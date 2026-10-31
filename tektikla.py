"""TekTıkla'yı başlatır:  python tektikla.py

Tanılama:  TekTikla.exe --selftest <link> <klasör>  (sonuç <klasör>\\selftest.txt dosyasına yazılır)
"""
import sys

from tektikla.tools import use_updated_ytdlp

use_updated_ytdlp()  # yt_dlp içe aktarılmadan önce olmalı


def selftest(url: str, out_dir: str) -> None:
    import os
    import traceback

    from tektikla import engine, tools
    from tektikla.config import Settings

    os.makedirs(out_dir, exist_ok=True)
    log = open(os.path.join(out_dir, "selftest.txt"), "w", encoding="utf-8")
    try:
        log.write(f"yt-dlp {engine.yt_dlp.version.__version__} @ {engine.yt_dlp.__file__}\n")
        missing = tools.missing_components()
        log.write(f"eksik: {missing}\n")
        if missing:
            tools.install_components(missing, lambda t, f: None)
        log.write(f"ffmpeg: {tools.find_ffmpeg()} | js: {list(tools.js_runtimes())}\n")
        settings = dict(Settings())
        info = engine.analyze(url, settings)
        log.write(f"analiz: {info.title} | {len(info.qualities)} kalite | {len(info.subtitles)} altyazı\n")
        sub = next((t for t in info.subtitles if not t.auto), None)
        for req in (
            engine.DownloadRequest(url=url, title=info.title, out_dir=out_dir, height=info.qualities[-1].height,
                                   sub_lang=sub and sub.lang, sub_mode="embed"),
            engine.DownloadRequest(url=url, title=info.title, out_dir=out_dir, mode="audio"),
        ):
            events = []
            engine.DownloadJob(req, settings, lambda k, **d: events.append((k, d)) if k != "progress" else None).run()
            log.write(f"{req.mode}: {events}\n")
        log.write("BITTI\n")
    except Exception:  # noqa: BLE001
        log.write(traceback.format_exc())
    log.close()


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--selftest":
        selftest(sys.argv[2], sys.argv[3])
    else:
        from tektikla.app import main
        main()
