import os
import json
import time
from src.ingestion import AudioDownloader
from src.transcription import Transcriber
from src.preprocessor import TextCleaner
from utils.config import VIDEO_SOURCES
from src.extractor import ConceptExtractor
from src.mapper import KnowledgeMapper
from src.study_path import StudyPathGenerator
from src.validate_dag import DAGValidator

def run_pipeline():
    # Initialize your modules
    downloader = AudioDownloader()
    transcriber = Transcriber(model_size="small") 
    extractor = ConceptExtractor()
    cleaner = TextCleaner()
    mapper = KnowledgeMapper()
    study_path_gen = StudyPathGenerator()

    print("--- Starting iREL Pedagogical Flow Extraction Pipeline ---")

    for video_id, source_url in VIDEO_SOURCES.items():
        print(f"\n>>> Processing Video: {video_id}")
        
        # 1) Ingestion (URL -> Local MP3)
        audio_path = f"data/raw_audio/{video_id}.mp3"
        if not os.path.exists(audio_path):
            print(f"  [1/5] Downloading audio for {video_id}...")
            audio_path = downloader.download(source_url, video_id)
        else:
            print(f"  [1/5] Audio file already exists. Skipping download.")

        # 2) Transcription (Local Audio -> Raw Text)
        raw_transcript_path = f"data/transcripts/{video_id}_raw.txt"
        os.makedirs("data/transcripts", exist_ok=True) # Ensure folder exists
        
        if not os.path.exists(raw_transcript_path):
            print(f"  [2/5] Transcribing audio...")
            # We pass the local audio_path to Whisper
            transcription_data = transcriber.transcribe(audio_path)
            transcript_text = transcription_data["text"]
            with open(raw_transcript_path, "w", encoding="utf-8") as f:
                f.write(transcript_text)
        else:
            print(f"  [2/5] Raw transcript found. Skipping transcription.")
            with open(raw_transcript_path, "r", encoding="utf-8") as f:
                transcript_text = f.read()

        # 3) Preprocessing (Cleaning Hinglish noise)
        cleaned_path = f"data/cleaned_text/{video_id}_cleaned.txt"
        os.makedirs("data/cleaned_text", exist_ok=True)
        
        if not os.path.exists(cleaned_path):
            print(f"  [3/5] Cleaning transcript and removing verbal fillers for {video_id}...")
            cleaned_text = cleaner.clean_hinglish(transcript_text)
            
            with open(cleaned_path, "w", encoding="utf-8") as f:
                f.write(cleaned_text)
        else:
            print(f"  [3/5] Cleaned text already exists. Skipping.")
            with open(cleaned_path, "r", encoding="utf-8") as f:
                cleaned_text = f.read()

        # 4) Concept Extraction & Validation Loop
        output_data_path = f"output/structured_data/{video_id}.json"
        os.makedirs("output/structured_data", exist_ok=True)
        
        validator = DAGValidator()
        structured_data = None
        valid_dag = False
        error_msg = None
        max_attempts = 2  # Primary attempt + 1 retry

        for attempt in range(max_attempts):
            # If JSON doesn't exist or we are retrying to fix a cycle
            if not os.path.exists(output_data_path) or (not valid_dag and attempt > 0):
                print(f"  [4/5] Extraction Attempt {attempt + 1} for {video_id}...")
                # Pass error feedback if this is a retry
                structured_data = extractor.extract_and_standardize(cleaned_text, error_feedback=error_msg)
            else:
                # Load existing file on the first attempt if it's there
                try:
                    with open(output_data_path, "r", encoding="utf-8") as f:
                        structured_data = json.load(f)
                except (json.JSONDecodeError, FileNotFoundError):
                    print(f"  [!] File corrupted or missing. Starting fresh extraction...")
                    structured_data = extractor.extract_and_standardize(cleaned_text)

            # Validate the data using Graph Theory
            if structured_data:
                valid_dag, cycles = validator.validate(structured_data, video_id)
                
                if valid_dag:
                    with open(output_data_path, "w", encoding="utf-8") as f:
                        json.dump(structured_data, f, indent=4)
                    break # Exit loop early if successful
                else:
                    error_msg = f"Circular dependency detected: {cycles[0]}"
                    print(f"  [!] Logical error found. Feedback generated for retry...")
            
            if attempt < max_attempts - 1:
                time.sleep(5) # Brief pause before retry

        # 5) Relational Mapping & Visualization
        if valid_dag:
            print(f"  [5/5] Visualizing pedagogical flow for {video_id}...")
            visualization_path = mapper.generate_graph(structured_data, video_id)
            print(f"  >>> Success! View the flowchart at: {visualization_path}")

            # 6) Automatic Study Path Generation
            print(f"  [6/6] Generating study path for {video_id}...")
            os.makedirs("output/study_paths", exist_ok=True)
            study_path_data = study_path_gen.generate(structured_data, video_id)
            study_path_out = f"output/study_paths/{video_id}_study_path.json"
            with open(study_path_out, "w", encoding="utf-8") as f:
                json.dump(study_path_data, f, indent=4, ensure_ascii=False)

            # Print a quick human-readable summary to the console
            print(f"  >>> Study path saved to: {study_path_out}")
            print(f"  >>> Recommended learning order ({study_path_data['total_concepts']} concepts):")
            for item in study_path_data.get("recommended_sequence", []):
                prereqs = ", ".join(item["prerequisites"]) if item["prerequisites"] else "none"
                print(f"       {item['step']:>2}. {item['concept']:<30}  (prereqs: {prereqs})")

            print(f"  >>> Parallel learning groups ({study_path_data['metadata']['total_parallel_groups']} levels):")
            for group in study_path_data.get("parallel_groups", []):
                names = ", ".join(c["concept"] for c in group["concepts"])
                print(f"       {group['level_label']}: {names}")
        else:
            print(f"  [!] Failed to generate a valid DAG for {video_id} after {max_attempts} attempts.")

    print("\n--- Pipeline Run Complete ---")

if __name__ == "__main__":
    run_pipeline()