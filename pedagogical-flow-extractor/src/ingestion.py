import yt_dlp
import os

class AudioDownloader:
    def __init__(self, output_dir="data/raw_audio"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def download(self, youtube_url, video_id):
        output_path = os.path.join(self.output_dir, f"{video_id}")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,               # Prevents downloading entire playlists
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': output_path, 
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])
        
        return f"{output_path}.mp3"