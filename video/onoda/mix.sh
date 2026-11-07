#!/usr/bin/env bash
# Mix voice + music (ducked) and mux with rendered video -> final mp4
set -e; D=${1:-build}; OUT=${2:-$D/final.mp4}
ffmpeg -y -loglevel error -i $D/voice.wav -i $D/music.wav -filter_complex "
[0:a]aresample=44100,highpass=f=70,equalizer=f=3500:t=q:w=1.2:g=3,acompressor=threshold=-20dB:ratio=3:attack=5:release=120,aformat=channel_layouts=stereo,asplit=2[v][key];
[1:a]volume=0.55[m];
[m][key]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=350[md];
[v][md]amix=inputs=2:weights='1 0.8':normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]" -map "[a]" -c:a pcm_s16le $D/mix.wav
ffmpeg -y -loglevel error -i $D/video_noaudio.mp4 -i $D/mix.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart "$OUT"
ffprobe -v error -show_entries format=duration,size -of default=nw=1 "$OUT"
