from __future__ import annotations

_PATCHED: set[str] = set()


def apply_spotiflac_compat_patch() -> None:
    """
    Upstream SpotiFLAC (0.6.1+) reads opts.include_featuring for Tidal URLs but
    DownloadOptions omits the field. Patch DownloadOptions.__init__ so latest PyPI works.
    """
    for module_name in ("SpotiFLAC.downloader", "backend.downloader"):
        if module_name in _PATCHED:
            continue
        try:
            module = __import__(module_name, fromlist=["DownloadOptions", "SpotiflacDownloader"])
        except ImportError:
            continue

        opts_cls = getattr(module, "DownloadOptions", None)
        downloader_cls = getattr(module, "SpotiflacDownloader", None)
        if opts_cls is None or downloader_cls is None:
            continue

        if not getattr(opts_cls, "_include_featuring_patched", False):
            original_opts_init = opts_cls.__init__

            def _make_opts_init(orig):
                def patched_opts_init(self, *args, **kwargs):
                    orig(self, *args, **kwargs)
                    if not hasattr(self, "include_featuring"):
                        self.include_featuring = False

                return patched_opts_init

            opts_cls.__init__ = _make_opts_init(original_opts_init)
            opts_cls._include_featuring_patched = True

        if not getattr(downloader_cls, "_include_featuring_patched", False):
            original_run = downloader_cls.run

            def _make_run(orig):
                def patched_run(self, url, loop_minutes=None):
                    if not hasattr(self._opts, "include_featuring"):
                        self._opts.include_featuring = False
                    return orig(self, url, loop_minutes=loop_minutes)

                return patched_run

            downloader_cls.run = _make_run(original_run)
            downloader_cls._include_featuring_patched = True

        _PATCHED.add(module_name)
        print(f"[spotiflac] compat patch applied on {module_name}")


def reset_spotiflac_compat_patch() -> None:
    _PATCHED.clear()
