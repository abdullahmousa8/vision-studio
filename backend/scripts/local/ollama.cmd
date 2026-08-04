@echo off
rem ============================================================================
rem  Local Ollama launcher (Windows). Serves on localhost:11434.
rem  Logs to %BACKEND%\logs\ollama.log.
rem
rem  OLLAMA_GPU_LAYERS controls GPU offload:
rem    0   -> CPU only (reliable when desktop apps hold the VRAM)
rem    99  -> offload everything to the GPU (requires free VRAM)
rem ============================================================================

set "OLLAMA_EXE=C:\Users\abdul\AppData\Local\Programs\Ollama\ollama.exe"
set "BACKEND=D:\h\gemini-vision-studio\backend"

if not exist "%BACKEND%\logs" mkdir "%BACKEND%\logs"
if "%OLLAMA_GPU_LAYERS%"=="" set "OLLAMA_GPU_LAYERS=0"

"%OLLAMA_EXE%" serve > "%BACKEND%\logs\ollama.log" 2>&1
