from __future__ import annotations


def apply_spotiflac_compat_patch() -> None:
    """SpotiFLAC 0.6.1+ references opts.include_featuring but DownloadOptions omits the field."""
    if getattr(apply_spotiflac_compat_patch, "_done", False):
        return

    patched_any = False
    for module_name in ("SpotiFLAC.downloader", "backend.downloader"):
        try:
            module = __import__(module_name, fromlist=["SpotiflacDownloader"])
        except ImportError:
            continue

        downloader_cls = getattr(module, "SpotiflacDownloader", None)
        if downloader_cls is None or getattr(downloader_cls, "_include_featuring_patched", False):
            continue

        original_init = downloader_cls.__init__

        def _make_init(orig):
            def patched_init(self, opts):
                if not hasattr(opts, "include_featuring"):
                    opts.include_featuring = False
                orig(self, opts)

            return patched_init

        downloader_cls.__init__ = _make_init(original_init)
        downloader_cls._include_featuring_patched = True
        patched_any = True

    if patched_any:
        print("[spotiflac] compat patch applied (include_featuring=False)")

    apply_spotiflac_compat_patch._done = True
