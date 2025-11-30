import pathlib
import os
import time
import json
import yaml
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
from pydantic import BaseModel, Field
from google import genai
from google.genai.types import GenerateContentConfig
from google.genai import types
from dotenv import load_dotenv
from argparse import ArgumentParser

class Judgement(BaseModel):
    """
    Represents the AI's judgment about which outcome a comment indicates.
    
    Attributes:
        judgement: The predicted outcome - should be "Yes", "No", or "NEITHER"
        reasoning: A brief explanation of why this judgement was made
    """
    judgement: str = Field(
        description="The outcome prediction: 'Yes', 'No', or 'NEITHER'"
    )
    reasoning: str = Field(
        description="Brief explanation of the reasoning behind the judgement"
    )


# System prompt for the classification task
SYSTEM_PROMPT = """
<ROLE>
You are an expert analyst evaluating comments on prediction markets. Your task is to determine whether a comment indicates that a market will resolve to Outcome Yes or Outcome No.
</ROLE>

<INSTRUCTIONS>
Your analysis should consider:
1. Direct statements about what will or won't happen
2. Evidence or reasoning that supports one outcome over another
3. The commenter's apparent belief about the outcome
4. Context clues and implicit indicators in the language used
5. Any indications about the markets overall sentiment or consensus

Important guidelines:
- Do not rely on your own opinions or external knowledge; base your judgement solely on the content of the comment.
- Focus on what the comment indicates about the LIKELIHOOD of each outcome
- If the comment is neutral, off-topic, or doesn't provide clear indication, respond with "NEITHER"
- Consider the full context of the event title and description when interpreting the comment
- Look for substantive predictive content, not just casual discussion
- Be conservative: if the indication is weak or ambiguous, use "NEITHER"

Respond with your judgement ("Yes", "No", or "NEITHER") and a brief reasoning explaining your decision.
</INSTRUCTIONS>

<EXAMPLES>
1.
Event title: Conservatives win majority in Canadian election?
Event description: This market will resolve to "Yes" if the Conservative Party of Canada wins a majority of seats.
Comment: Pierre Betters rn: https://www.youtube.com/shorts/l3ZKvcrN2O8
Judgement: NEITHER
Reasoning: The comment referst to person named Pierre Betters and provides a YouTube link, but does not provide any information or indication about the likelihood of the Conservative Party winning a majority in the Canadian election.

2.
Event title: Pakistan air/missile strike on Indian soil by Friday?
Event description: This market will resolve to "Yes" if Pakistan initiates an airstrike or missile strike on Indian soil between May 7 and May 9, 2025.
Comment: Still no qualifying strike has taken place.
Judgement: No
Reasoning: The comment indicates that no qualifying strike has taken place yet, which gives reason to believe that Pakistan will not initiate an airstrike or missile strike on Indian soil within the specified timeframe.

3.
Event title: Will the US ban TikTok by the end of 2025?
Event description: This market will resolve to "Yes" if the United States government implements a ban on the TikTok app by December 31, 2025.
Comment: Some No will sell
Judgement: Yes
Reasoning: The comment suggests that some people who predicted a "No" outcome will sell their positions, indicating a lack of confidence in the "No" outcome.

4.
Event title: Fordow nuclear facility destroyed before July?
Event description: This market will resolve to "Yes" if the Fordow nuclear facility in Iran is destroyed or rendered inoperable before July 1, 2025.
Comment: Game Over = "Destroyed" directly from CIA director https://twitter.com/CIADirector/status/1937964888967823652
Judgement: Yes
Reasoning: The comment references a statement from the CIA director indicating that the Fordow nuclear facility has been destroyed, which directly supports the "Yes" outcome for this market.

5.
Event title: Major cyberattack on Iran in June?
Event description: This market will resolve to "Yes" if there is a major cyberattack on Iran during the month of June 2025.
Comment: we are so cooked right?
Judgement: NEITHER
Reasoning: The comment expresses concern about the outcome, HOWEVER we do not know if the commenter has betted on Yes or No, therefore we cannot determine for which position they are indicating, so we choose NEITHER.
"""


def setup_gemini_client(api_key: str = None):
    """
    Configure the Gemini API client.
    
    Args:
        api_key: Google API key. If None, reads from GEMINI_API_KEY or GOOGLE_API_KEY environment variable
    """
    if api_key is None:
        api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    if not api_key:
        raise ValueError("API key must be provided or set in GEMINI_API_KEY/GOOGLE_API_KEY environment variable")
    return genai.Client(api_key=api_key)


def test_with_samples(df: pd.DataFrame, n_samples: int = 10, model_name: str = "gemini-2.5-flash"):
    """
    Test the labeling system with a sample of prompts.
    
    Args:
        df: DataFrame containing labeling_prompt column
        n_samples: Number of samples to test
        model_name: Name of the Gemini model to use
        
    Returns:
        List of tuples containing (id, prompt, judgement_object)
    """
    client = setup_gemini_client()
        
    # Sample random prompts
    samples = df.sample(n=min(n_samples, len(df)))
    results = []
    
    print(f"Testing with {len(samples)} samples...\n")
    
    for idx, row in samples.iterrows():
        prompt_id = row['id']
        prompt = row['labeling_prompt']
        
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=Judgement.model_json_schema(),
                    system_instruction=SYSTEM_PROMPT,
                ),
            )
            judgement = Judgement.model_validate_json(response.text)

            results.append((prompt_id, prompt, judgement))
            
            print(f"ID: {prompt_id}")
            print(f"Prompt: {prompt}")
            print(f"Judgement: {judgement.judgement}")
            print(f"Reasoning: {judgement.reasoning}")
            print("-" * 80)
            
        except Exception as e:
            print(f"Error processing ID {prompt_id}: {e}")
            print("-" * 80)
    
    return results


def uppercase_types(schema):
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key == "type" and isinstance(value, str):
                schema[key] = value.upper()
            else:
                uppercase_types(value)
    elif isinstance(schema, list):
        for item in schema:
            uppercase_types(item)
    return schema

def create_batch_requests(df: pd.DataFrame, inline: bool) -> List[Dict[str, Any]]:
    """
    Convert DataFrame prompts into inline batch request format for Gemini API.
    
    Args:
        df: DataFrame with 'id' and 'labeling_prompt' columns
        batch_name: Name identifier for the batch
        
    Returns:
        List of request dictionaries in Gemini batch API format
    """
    prompts = df['labeling_prompt'].tolist()
    if inline:
        cfg = GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=Judgement.model_json_schema(),
                        system_instruction=SYSTEM_PROMPT,
                    ).to_json_dict()
        return [
            {
                "contents": [{
                    "parts": [{
                        "text": prompt,
                    }],
                    "role": "user"
                }],
                "config": cfg
            }
            for prompt in prompts
        ]
    else:
        structured_output_schema = Judgement.model_json_schema()
        # find all type keys and upper their values
        structured_output_schema = uppercase_types(structured_output_schema)
        return [
            {
                "request":{
                    "contents": [{
                        "parts": [{
                            "text": prompt,
                        }],
                        "role": "user"
                    }],
                    "generationConfig": {
                        "responseMimeType": "application/json",
                        "responseSchema": structured_output_schema,
                    },
                    "systemInstruction": {
                        "parts": [{
                            "text": SYSTEM_PROMPT,
                        }],
                    }
                }
            }
            for prompt in prompts
        ]


def submit_batch_job(batch_requests: List[Dict[str, Any]] | None = None, batch_file_name: str | None = None, model_name: str = "gemini-2.5-flash", batch_name: str = "labeling_batch") -> types.BatchJob:
    """
    Submit a batch job to Gemini API.
    
    Args:
        batch_requests: List of request dictionaries
        batch_file_name: GCS file name containing batch requests (if not using inline requests)
        model_name: Name of the Gemini model to use
        batch_name: Name identifier for the batch

    Returns:
        BatchJob object representing the submitted job
    """
    client = setup_gemini_client()

    src = None
    if batch_requests is not None:
        src = batch_requests
    elif batch_file_name is not None:
        src = batch_file_name
    else:
        raise ValueError("Either batch_requests or batch_file_name must be provided")

    return client.batches.create(
        model=model_name,
        src=src,
        config = {"display_name": batch_name}
    )


def upload_requests_as_jsonl(df: pd.DataFrame, file_path: str):
    """
    Write batch requests to a JSONL file.
    
    Args:
        batch_requests: List of request dictionaries
        file_path: Path to the output JSONL file
    """
    ids = df['id'].tolist()

    if os.path.exists(file_path):
        print(f"File {file_path} already exists. Loading existing requests.")
        batch_requests = [json.loads(line) for line in open(file_path, 'r').readlines()]
    else:
        batch_requests = create_batch_requests(df, inline=False)

    requests_with_ids = [
        {"key": str(id_), **request} for id_, request in zip(ids, batch_requests)
    ]

    with open(file_path, 'w') as f:
        for request in requests_with_ids:
            json_line = json.dumps(request)
            f.write(json_line + '\n')

    client = setup_gemini_client()

    # 2. Upload JSONL file to File API.
    result = client.files.upload(
        file=file_path,
        config=types.UploadFileConfig(display_name='batch-input-file', mime_type='application/jsonl')
    )
    print(f"Uploaded file ID: {result.name}")
    return result

def poll_batch_job(batch_job_inline: types.BatchJob, poll_interval: int = 30, max_wait: int = 3600) -> types.BatchJob:
    """
    Poll a batch job until completion or timeout using REST API.
    
    Args:
        job_name: The job name/ID returned from submit_batch_job
        poll_interval: Seconds to wait between polls
        max_wait: Maximum seconds to wait before giving up
        
    Returns:
        Final job status dictionary
    """
    job_name = batch_job_inline.name
    print(f"Polling status for job: {job_name}")
    client = setup_gemini_client()

    time_started = time.time()
    time_elapsed = 0
    while time_elapsed < max_wait:
        batch_job_inline = client.batches.get(name=job_name)
        if batch_job_inline.state.name in ('JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED', 'JOB_STATE_CANCELLED'):
            break
        print(f"Job not finished. Current state: {batch_job_inline.state.name}. Waiting {poll_interval} seconds...")
        time.sleep(poll_interval)
        time_elapsed = time.time() - time_started

    if time_elapsed >= max_wait and batch_job_inline.state.name not in ('JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED', 'JOB_STATE_CANCELLED'):
        print(f"Max wait time of {max_wait} seconds exceeded. Exiting application.")
        exit(1)

    else:
        print(f"Job finished with state: {batch_job_inline.state.name}")
        if batch_job_inline.state.name == 'JOB_STATE_FAILED':
            print(f"Error: {batch_job_inline.error}")
        return batch_job_inline
    
def get_job(job_name: str) -> types.BatchJob:
    """
    Get the current status of a batch job using REST API.
    
    Args:
        job_name: The job name/ID returned from submit_batch_job
        
    Returns:
        Current BatchJob object
    """
    client = setup_gemini_client()
    batch_job = client.batches.get(name=job_name)
    return batch_job

def save_raw_file_results(batch_job: types.BatchJob, start: Optional[int] = None, end: Optional[int] = None):
    """
    Parse batch job results from JSONL file into a DataFrame.
    
    Args:
        batch_job: Completed BatchJob object
        start: Start index for subset processing (included in filename)
        end: End index for subset processing (included in filename)

    """

    if batch_job.state.name == 'JOB_STATE_SUCCEEDED':
        # The output is in another file.
        result_file_name = batch_job.dest.file_name

        client = setup_gemini_client()

        print("\nDownloading and parsing result file content...")
        file_content_bytes = client.files.download(file=result_file_name)
        file_content = file_content_bytes.decode('utf-8')

        repo = pathlib.Path(os.getenv('REPO'))

        os.makedirs(repo / 'gemini_results', exist_ok=True)
        sanitized_name = result_file_name.replace('/', '_')
        
        # Add start/end to filename if provided
        if start is not None and end is not None:
            sanitized_name += f'_rows_{start}_{end}'
        
        sanitized_name += '.jsonl'
        result_path = repo / 'gemini_results' / sanitized_name
        print(f"Raw results saved to file: {result_path}")
        # dump file content to local file
        with open(result_path, 'w') as f:
            f.write(file_content)

        return result_path.as_posix()
    else:
        print(f"Job did not succeed. Final state: {batch_job.state.name}")
        
def parse_file_results(file_path: str, start: Optional[int] = None, end: Optional[int] = None) -> pd.DataFrame:
        result_path = pathlib.Path(file_path) 
        with open(result_path, 'r') as f:
            file_content = f.read()
        # Parse JSONL and extract judgements
        print("\nParsing judgements from results...")
        parsed_results = []
        
        for line in file_content.strip().split('\n'):
            try:
                result_obj = json.loads(line)
                key = result_obj.get('key')
                
                # Extract the judgement text from the response
                if 'response' in result_obj and 'candidates' in result_obj['response']:
                    candidates = result_obj['response']['candidates']
                    if candidates and len(candidates) > 0:
                        parts = candidates[0].get('content', {}).get('parts', [])
                        if parts and len(parts) > 0:
                            judgement_json = parts[0].get('text', '')
                            
                            # Parse the judgement JSON
                            try:
                                judgement_data = json.loads(judgement_json)
                                parsed_results.append({
                                    'key': key,
                                    'judgement': judgement_data.get('judgement'),
                                    'reasoning': judgement_data.get('reasoning'),
                                    'status': 'success'
                                })
                            except json.JSONDecodeError as e:
                                print(f"Failed to parse judgement JSON for key {key}: {e}")
                                parsed_results.append({
                                    'key': key,
                                    'judgement': None,
                                    'reasoning': None,
                                    'status': 'parse_error'
                                })
                else:
                    # Check for errors
                    error_msg = result_obj.get('error', 'Unknown error')
                    parsed_results.append({
                        'key': key,
                        'judgement': None,
                        'reasoning': None,
                        'status': f'error: {error_msg}'
                    })
                    
            except json.JSONDecodeError as e:
                print(f"Failed to parse line: {e}")
                continue
        
        # Convert to DataFrame and save as parquet
        df_results = pd.DataFrame(parsed_results)
        
        # Add start/end to parquet filename if provided
        parquet_name = result_path.stem
        if start is not None and end is not None:
            # Remove existing _rows suffix if present from jsonl filename
            if '_rows_' not in parquet_name:
                parquet_name += f'_rows_{start}_{end}'
        parquet_path = result_path.parent / f"{parquet_name}.parquet"
        
        df_results.to_parquet(parquet_path, index=False)
        
        print(f"Parsed {len(parsed_results)} results")
        print(f"Saved parsed results to: {parquet_path}")
        print(f"\nResults summary:")
        print(df_results['status'].value_counts())
        
        return df_results


def parse_inline_results(batch_job_inline: types.BatchJob):
    """
    Parse batch job results from JSONL file into a DataFrame.
    
    Args:
        batch_job: Completed BatchJob object
        
    Returns:
        DataFrame with columns: id, judgement, reasoning, status
    """
    if batch_job_inline.state.name == 'JOB_STATE_SUCCEEDED':
        print("\nResults are inline:")
    # The results are in the `inlined_responses` field.
    for i, inline_response in enumerate(batch_job_inline.dest.inlined_responses):
        print(f"\n--- Response {i+1} ---")

        # Check for a successful response
        if inline_response.response:
            # The .text property is a shortcut to the generated text.
            try:
                print(inline_response.response.text)
            except AttributeError:
                # Fallback to printing the full response if .text isn't available
                print(inline_response.response)

        # Check for an error in this specific request
        elif inline_response.error:
            print(f"Error: {inline_response.error}")

def check_request_size(df: pd.DataFrame):
    batch_requests = create_batch_requests(df, inline=False)
    # write batch_requests to json file and check its size
    with open('batch_requests.json', 'w') as f:
        json.dump(batch_requests, f)
    file_size = os.path.getsize('batch_requests.json')
    print(f"Batch requests JSON file size: {file_size / (1024 * 1024):.2f} MB")

def save_batch_job_id(batch_job: types.BatchJob):
        repo = pathlib.Path(os.getenv('REPO'))
        os.makedirs(repo / 'gemini_results', exist_ok=True)
        job_id_file = repo / 'gemini_results' / 'last_batch_job_id.txt'
        with open(job_id_file, 'a') as f:
            f.write(batch_job.name)
        print(f"Saved batch job ID to: {job_id_file}")


def main():
    parser = ArgumentParser(description="Gemini API-based labeling system for Polymarket comment sentiment analysis.")
    parser.add_argument('--config', type=str, required=True, help='Path to YAML configuration file')
    args = parser.parse_args()

    print('Loading environment variables from .env file:', load_dotenv())
    
    # Load YAML configuration
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)
    
    print(f"Loaded configuration from {args.config}")
    print(f"Config: {config}\n")
    
    # Extract config parameters
    job_id = config.get('job_id')
    use_file_api = config.get('use_file_api', False)
    file_path = config.get('file_path')
    start = config.get('start')
    end = config.get('end')
    data_file = config.get('data_file', 'comment_market_labeling_prompts.parquet')
    poll_interval = config.get('poll_interval', 30)
    batch_name = config.get('batch_name', 'labeling_batch')
    model_name = config.get('model_name', 'gemini-2.5-flash')
    
    # If job_id is provided, poll existing job
    if job_id:
        print(f"Polling existing job ID: {job_id}")
        batch_job = get_job(job_id)
        final_job = poll_batch_job(batch_job, poll_interval=poll_interval)
        if use_file_api:
            results_path = save_raw_file_results(final_job, start=start, end=end)
            results_df = parse_file_results(results_path, start=start, end=end)
        else:
            parse_inline_results(final_job)
        exit(0)

    # Load data
    data_path = pathlib.Path(os.getenv('REPO')) / data_file
    print("Loading data...")
    df = pd.read_parquet(data_path)
    print(f"Loaded {len(df)} prompts\n")
    
    # Apply start/end slicing if specified
    if start is not None and end is not None:
        print(f"Processing subset: rows {start} to {end}")
        df = df.iloc[start:end]
        print(f"Subset size: {len(df)} prompts\n")
    elif start is not None or end is not None:
        raise ValueError("Both start and end must be specified together")
    
    print("\nSubmitting batch job...")

    if use_file_api:
        # Construct file path with start/end if provided
        if file_path is None:
            raise ValueError("file_path must be specified when use_file_api is True")
        
        destination = pathlib.Path(os.getenv('REPO')) / file_path
        
        # Add start/end to file path if specified
        if start is not None and end is not None:
            dest_stem = destination.stem
            dest_suffix = destination.suffix
            destination = destination.parent / f"{dest_stem}_rows_{start}_{end}{dest_suffix}"
        
        print(f"Using File API with JSONL file at: {destination}")
        # Write batch requests to JSONL file
        upload_response = upload_requests_as_jsonl(df, file_path=str(destination))
        batch_job = submit_batch_job(
            batch_file_name=upload_response.name,
            batch_name=batch_name,
            model_name=model_name
        )

        save_batch_job_id(batch_job)

        final_job = poll_batch_job(batch_job, poll_interval=poll_interval)
        results_path = save_raw_file_results(final_job, start=start, end=end)
        results_df = parse_file_results(results_path, start=start, end=end)
    else:
        batch_requests = create_batch_requests(df, inline=True)
        batch_job = submit_batch_job(batch_requests, batch_name=batch_name, model_name=model_name)
        final_job = poll_batch_job(batch_job, poll_interval=poll_interval)
        parse_inline_results(final_job)

if __name__ == "__main__":
    main()