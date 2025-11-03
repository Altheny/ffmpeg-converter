# FFmpeg Converter v0.2.0

**Prosty, ale skuteczny konwerter wideo/audio z GUI w Pythonie (Tkinter).**  
Bez instalowania Pythona – wystarczy `.exe`!

## Funkcje
- Konwersja do **H.265** (CRF 19–33, preset od ultrafast do veryslow)
- Skalowanie: **4K, Full HD, HD, SD, Mobile, 50%, 25%**
- Ekstrakcja **MP3** (128 kbps)
- **Tray icon** – minimalizuje do paska zadań
- **Paski postępu** (całkowity + plik)
- **Tryby z opisami** (bez „+” w nazwach)
- **Debug mode** (`--debug` → log w `debug.log`)
- **Style** (menu → ciemny/jasny – plik `.css` w `styles/`)

## Wymagania
- **Windows** (testowane na 10/11)
- **FFmpeg** w PATH (pobierz: [ffmpeg.org](https://ffmpeg.org/download.html))
- Python 3.8+ (jeśli uruchamiasz `.pyw`)
- `pip install appdirs pillow pystray`

## Użycie
1. Pobierz `.exe` z **Releases** lub uruchom `ffmpeg_gui.pyw`
2. Wybierz **tryb**, **CRF**, **preset**
3. Wskaż **katalog** z plikami
4. Kliknij **START**

> **Uwaga:** Pliki wyjściowe: `nazwa_ff.mkv` lub `nazwa_ff.mp3`

## Budowanie .exe
```bash
pip install pyinstaller
pyinstaller --onefile --noconsole ffmpeg_gui.pyw
```

## Autor:
>  Altheny C.&.E in cooperation with artificial intelligence
