import whisper
import os

class Transcriber:
    def __init__(self, model_size="small"):
        # 'small' is a good choice for faster inference with slightly lower accuracy
        print(f"Loading Whisper {model_size} model...")
        self.model = whisper.load_model(model_size)

    def transcribe(self, audio_path):
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found at {audio_path}")
        
        # Whisper handles code-switching automatically
        result = self.model.transcribe(audio_path)
        # return the full result including segments/timestamps
        return {
            "text": result["text"],
            "segments": result["segments"] # This contains start/end times
        }