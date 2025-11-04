import { Injectable, Logger } from '@nestjs/common';
import { PolymarketClientService } from './polymarket-client.service';
import { RateLimiterService } from './rate-limiter.service';
import { PrismaService } from '../prisma/PrismaService';
import { Config } from '../config/config';
import { Comment } from 'polymarket-data';
import { type Prisma } from '@prisma/client';

@Injectable()
export class CommentScraperService {
  private readonly logger = new Logger(CommentScraperService.name);

  constructor(
    private readonly polymarketClient: PolymarketClientService,
    private readonly rateLimiter: RateLimiterService,
    private readonly prisma: PrismaService,
    private readonly config: Config,
  ) {}

  /**
   * Scrape comments for all markets with incremental pagination
   * Returns the number of comments scraped
   */
  async scrapeAllComments(): Promise<{
    commentsScraped: number;
    marketsProcessed: number;
    errors: string[];
  }> {
    const startTime = Date.now();
    this.logger.log('Starting comment scraping...');

    let commentsScraped = 0;
    let marketsProcessed = 0;
    const errors: string[] = [];

    try {
      // Get all events
      const events = await this.prisma.event.findMany({
        select: { id: true },
      });

      this.logger.log(`Found ${events.length} markets to process`);

      // Process each market
      for (const event of events) {
        try {
          const result = await this.scrapeCommentsForEvent(event.id);
          commentsScraped += result.commentsScraped;
          marketsProcessed++;

          if (this.config.scraper.verboseLogging) {
            this.logger.debug(
              `Market ${event.id}: ${result.commentsScraped} new comments`,
            );
          }
        } catch (error) {
          const errorMsg = `Failed to scrape comments for market ${event.id}: ${(error as Error).message}`;
          this.logger.error(errorMsg);
          errors.push(errorMsg);
        }
      }
    } catch (error) {
      const errorMsg = `Failed to fetch markets: ${(error as Error).message}`;
      this.logger.error(errorMsg);
      errors.push(errorMsg);
    }

    const duration = Date.now() - startTime;
    this.logger.log(
      `Comment scraping completed: ${commentsScraped} comments from ${marketsProcessed} markets in ${duration}ms`,
    );

    if (errors.length > 0) {
      this.logger.warn(`Encountered ${errors.length} errors during scraping`);
    }

    return { commentsScraped, marketsProcessed, errors };
  }

  /**
   * Scrape comments for a specific market with incremental pagination
   */
  async scrapeCommentsForEvent(eventId: string): Promise<{
    commentsScraped: number;
  }> {
    let commentsScraped = 0;
    const limit = this.config.scraper.commentsBatchSize;

    // Parse market ID to number (Polymarket API expects numeric IDs)
    let eventIdNum: number;
    try {
      eventIdNum = parseInt(eventId, 10);
      if (isNaN(eventIdNum)) {
        this.logger.warn(
          `Market ID ${eventId} is not numeric, skipping comments`,
        );
        return { commentsScraped: 0 };
      }
    } catch (error) {
      this.logger.warn(
        `Failed to parse market ID ${eventId}, skipping comments`,
      );
      return { commentsScraped: 0 };
    }

    // Get checkpoint for this market
    let checkpoint = await this.prisma.commentCheckpoint.findUnique({
      where: {
        id: eventIdNum,
      },
    });

    let offset = checkpoint?.lastOffset || 0;
    let hasMore = true;

    while (hasMore) {
      try {
        // Fetch comments with rate limiting
        const comments = await this.rateLimiter.executeComments(async () => {
          return await this.polymarketClient.withRetry(
            () =>
              this.polymarketClient.getClient().gamma.comments.listComments({
                parent_entity_type: 'Event',
                parent_entity_id: eventIdNum,
                limit,
                offset,
              }),
            `Fetch comments for event ${eventId} offset=${offset}`,
          );
        });

        if (!comments || comments.length === 0) {
          hasMore = false;
          break;
        }

        // Save comments
        for (const comment of comments) {
          try {
            await this.saveComment(comment, eventId);
            commentsScraped++;
          } catch (error) {
            this.logger.error(
              `Failed to save comment ${comment.id}: ${(error as Error).message}`,
            );
          }
        }

        // Update checkpoint
        offset += comments.length;
        await this.upsertCheckpoint(eventId, offset, commentsScraped);

        // Check if we should continue
        if (comments.length < limit) {
          hasMore = false;
        }
      } catch (error) {
        this.logger.error(
          `Failed to fetch comments for market ${eventId} at offset ${offset}: ${(error as Error).message}`,
        );
        hasMore = false;
      }
    }

    return { commentsScraped };
  }

  /**
   * Save a single comment to the database
   */
  private async saveComment(
    commentData: Comment,
    eventId: string,
  ): Promise<void> {
    const parseDate = (dateStr: string | null | undefined): Date => {
      if (!dateStr) return new Date();
      try {
        return new Date(dateStr);
      } catch {
        return new Date();
      }
    };

    const commentCreateInput: Prisma.CommentCreateInput = {
      id: commentData.id,
      body: commentData.body,
      replyAddress: commentData.replyAddress,
      parentEntityType: commentData.parentEntityType,
      reactionCount: commentData.reactionCount,
      reportCount: commentData.reportCount,
      createdAt: parseDate(commentData.createdAt),
      updatedAt: parseDate(commentData.updatedAt),
      event: {
        connect: {
          id: eventId,
        },
      },
      profile: {
        connectOrCreate: {
          where: {
            address: commentData.profile.baseAddress,
          },
          create: {
            address: commentData.profile.baseAddress,
            baseAddress: commentData.profile.baseAddress,
            name: commentData.profile.name,
            pseudonym: commentData.profile.pseudonym,
            displayUsernamePublic: commentData.profile.displayUsernamePublic,
            proxyWallet: commentData.profile.proxyWallet,
            bio: commentData.profile.bio,
            profileImage: commentData.profile.profileImage,
            isCreator: commentData.profile.isCreator,
            isMod: commentData.profile.isMod,
          },
        },
      },
      // Set parent comment relationship if this is a reply
      ...(commentData.parentCommentID && {
        parentComment: {
          connect: {
            id: commentData.parentCommentID,
          },
        },
      }),
    };

    await this.prisma.comment.upsert({
      where: { id: commentData.id },
      create: commentCreateInput,
      update: commentCreateInput,
    });

    // Save reactions for this comment
    if (commentData.reactions && commentData.reactions.length > 0) {
      for (const reaction of commentData.reactions) {
        try {
          if (reaction.id && reaction.userAddress && reaction.reactionType) {
            await this.prisma.commentReaction.upsert({
              where: { id: reaction.id },
              create: {
                id: reaction.id,
                reactionType: reaction.reactionType,
                userAddress: reaction.userAddress,
                commentID: commentData.id,
              },
              update: {
                reactionType: reaction.reactionType,
                userAddress: reaction.userAddress,
                commentID: commentData.id,
              },
            });
          }
        } catch (error) {
          this.logger.error(
            `Failed to save reaction ${reaction.id} for comment ${commentData.id}: ${(error as Error).message}`,
          );
        }
      }
    }
  }

  /**
   * Upsert checkpoint for a market
   */
  private async upsertCheckpoint(
    eventId: string,
    offset: number,
    totalFetched: number,
  ): Promise<void> {
    await this.prisma.commentCheckpoint.upsert({
      where: { eventId },
      create: {
        eventId,
        lastOffset: offset,
        totalFetched,
      },
      update: {
        lastOffset: offset,
        totalFetched,
      },
    });
  }
}
