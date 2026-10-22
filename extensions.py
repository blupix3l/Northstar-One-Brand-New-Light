"""
NorthStar Extension Manager
===========================

A minimal, self-contained extension system built on QtWebEngine's
``QWebEngineScript`` content-script mechanism.

QtWebEngine deliberately does NOT expose Chrome's full extension API
(background pages, ``browser.*`` API surface, browser actions, omnibox,
etc.).  The only realistic, engine-blessed way to let third-party code
affect pages is a *content script* — the exact equivalent of
manifest.json ``content_scripts``.

This module therefore models an extension as a folder containing:

    manifest.json     — metadata + declared content scripts
    background.js     — (optional, reserved) main content script
    content/<name>.js — each declared content script file

``manifest.json`` schema (forward-compatible subset of the Chrome MV3
manifest that QtWebEngine can actually honour):

    {
      "id": "my-extension",
      "name": "My Extension",
      "version": "1.0.0",
      "description": "...",
      "enabled": true,
      "content_scripts": [
        {
          "matches": ["*://*/*"],          // URL patterns (see _url_match)
          "js": ["content/darken.js"],     // relative to the ext folder
          "run_at": "document_start",      // document_start | document_idle
          "all_frames": false
        }
      ]
    }

The manager:
  * installs an extension  -> copies source into <data>/extensions/<id>/
  * tracks state in         -> <data>/extensions/registry.json
  * injects/removes scripts -> via QWebEngineProfile.scripts()
  * persists enabled/disabled state across restarts

BACKEND ARCHITECTURE
--------------------

Runtime behaviour is delegated to a *backend*.  ``ExtensionManager`` is a
thin facade that selects the best backend supported by the installed Qt:

    NativeBackend
        Uses QtWebEngine's real extension runtime
        (``QWebEngineProfile::extensionManager``, MV3) — available on
        QtWebEngine >= 6.10.  Installs/unpacks real MV3 extensions and runs
        them with full service-worker / chrome.* support.

    ContentScriptBackend
        The engine-blessed fallback for QtWebEngine < 6.10: injects each
        extension's declared ``content_scripts`` via ``QWebEngineScript``.

Public callers (UI code, ``NorthStar_v1.py``) only ever talk to
``ExtensionManager`` and never to a backend directly, so swapping backends
later is invisible to them.  The facade emits ``ExtensionManager.changed``
whenever an install/enable/remove completes so the UI can refresh.

Only newly-created pages pick up content scripts (QWebEngineScript is
injected at DocumentCreation by Chromium).  To apply an extension to an
existing tab, reload that tab.
"""

import os
import json
import glob
import shutil
import time
import uuid as _uuid_mod
import fnmatch

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtWebEngineCore import QWebEngineScript


# ─────────────────────────────────────────────
#  REGISTRY / STATE STORAGE
# ─────────────────────────────────────────────
def _extensions_root(data_dir: str) -> str:
    root = os.path.join(data_dir, "extensions")
    os.makedirs(root, exist_ok=True)
    return root


def _registry_path(data_dir: str) -> str:
    return os.path.join(_extensions_root(data_dir), "registry.json")


def _load_registry(data_dir: str) -> dict:
    try:
        with open(_registry_path(data_dir), "r", encoding="utf-8") as f:
            reg = json.load(f)
            if isinstance(reg, dict):
                return reg
    except Exception:
        pass
    return {}


def _save_registry(data_dir: str, registry: dict) -> None:
    try:
        with open(_registry_path(data_dir), "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2)
    except Exception:
        pass


def _generate_id(name: str) -> str:
    """Deterministic-ish id that stays stable across reinstalls."""
    slug = "".join(ch for ch in name.lower() if ch.isalnum() or ch in "-_")
    slug = slug[:32] or "ext"
    return f"{slug}-{_uuid_mod.uuid4().hex[:6]}"


def _qt_version() -> tuple:
    """Return the running Qt version as (major, minor, patch), or (0,0,0)."""
    try:
        from PyQt6.QtCore import QT_VERSION_STR as _v
        parts = _v.split(".")
        return tuple(int(p) for p in parts[:3])
    except Exception:
        return (0, 0, 0)


# ─────────────────────────────────────────────
#  CONTENT-SCRIPT URL MATCHING (simplified)
# ─────────────────────────────────────────────
def _url_match(pattern: str, url: str) -> bool:
    """Match a Chrome-style match pattern (subset) against a URL string.

    Supports:  <scheme>://<host>/<path>, with `*` wildcards.
    Example:   *://*.example.com/* , https://*/foo*, http://localhost/*
    Returns True if no matches are declared (treat as match-all).
    """
    if not pattern:
        return False
    try:
        u = QUrl(url)
        scheme = u.scheme()
        host = u.host()
        path = u.path() or "/"
    except Exception:
        return False

    # Split pattern into scheme://host/path
    rest = pattern.split("://", 1)
    if len(rest) != 2:
        return False
    p_scheme, rest2 = rest[0], rest[1]
    if "/" in rest2:
        p_host, p_path = rest2.split("/", 1)
        p_path = "/" + p_path
    else:
        p_host, p_path = rest2, "/"

    if p_scheme != "*" and p_scheme != scheme:
        return False
    if p_host != "*" and not fnmatch.fnmatch(host, p_host):
        return False
    if p_path != "*" and not fnmatch.fnmatch(path, p_path):
        return False
    return True


# ─────────────────────────────────────────────
#  BACKEND INTERFACE
# ─────────────────────────────────────────────
class ExtensionBackend:
    """Interface implemented by extension runtimes.

    ``ExtensionManager`` selects the strongest available backend at startup
    and delegates every public operation to it.  Keep the method surface
    stable so the UI never depends on which backend is active.
    """

    name: str = "abstract"

    @staticmethod
    def available() -> bool:
        """True if this backend can run on the installed Qt."""
        raise NotImplementedError

    def list_extensions(self) -> list:
        raise NotImplementedError

    def get_extension(self, ext_id: str) -> dict | None:
        raise NotImplementedError

    def is_enabled(self, ext_id: str) -> bool:
        raise NotImplementedError

    def install_from_dir(self, source_dir: str) -> dict | None:
        raise NotImplementedError

    def remove(self, ext_id: str) -> bool:
        raise NotImplementedError

    def set_enabled(self, ext_id: str, enabled: bool) -> bool:
        raise NotImplementedError

    def install_all_enabled(self):
        raise NotImplementedError

    def take_last_error(self) -> str | None:
        """Return and clear the most recent reported error, if any."""
        return None


# ─────────────────────────────────────────────
#  NATIVE BACKEND (QtWebEngine >= 6.10, MV3)
# ─────────────────────────────────────────────
class NativeBackend(ExtensionBackend):
    """Full MV3 support built on ``QWebEngineProfile::extensionManager``.

    QtWebEngine added real extension support in 6.10: MV3 extensions are
    installed per-profile via the ``QWebEngineExtensionManager`` (MV3 only),
    service workers and ``chrome.*`` APIs run for real, and installed
    extensions are re-loaded automatically at startup.

    Key behaviours of the Qt API we lean on here:

      * ``installExtension(path)`` accepts a directory *or* a zip/crx file
        whose top level contains ``manifest.json``; it is asynchronous and
        reports via the ``installFinished`` signal (success is read from
        ``QWebEngineExtensionInfo.isInstalled()``).
      * Installed extensions load at startup in the *disabled* state, so we
        persist each extension's enabled intent in the shared registry and
        re-apply it (``setExtensionEnabled``) at startup / on every load to
        survive restarts.
      * ``extensions()`` also includes Chromium built-ins (Hangouts, PDF);
        we filter those out via ``isInstalled()``.
      * ``loadExtension`` (dev mode, not persisted) exists but is unused —
        we always install, so extensions survive restarts by themselves.
    """

    name: str = "native"
    REQUIRED_QT: tuple = (6, 10, 0)

    @staticmethod
    def available() -> bool:
        if _qt_version() < NativeBackend.REQUIRED_QT:
            return False
        try:
            from PyQt6.QtWebEngineCore import QWebEngineProfile
            return hasattr(QWebEngineProfile, "extensionManager")
        except Exception:
            return False

    def __init__(self, data_dir: str, profile, notify=None):
        if not NativeBackend.available():
            raise NotImplementedError(
                "Native extension backend requires QtWebEngine >= 6.10 "
                f"(running Qt {'.'.join(map(str, _qt_version()))})."
            )
        self._data_dir = data_dir
        self._profile = profile
        self._notify = notify or (lambda: None)
        self._root = _extensions_root(data_dir)
        self._registry = _load_registry(data_dir)
        self._last_error = None
        self._intent_applied: set = set()

        # QWebEngineExtensionInfo signal payloads are snapshots, so keep a
        # handle we can also pass back to setExtensionEnabled()/uninstall().
        self._manager = profile.extensionManager()
        self._manager.installFinished.connect(self._on_install_finished)
        self._manager.loadFinished.connect(self._on_load_finished)
        self._manager.uninstallFinished.connect(self._on_uninstall_finished)

    # ── Registry helpers (shared layout with the content-script backend) ──
    def _intent(self, ext_id: str, default: bool = True) -> bool:
        return bool(self._registry.get(ext_id, {}).get("intent_enabled", default))

    def _set_intent(self, ext_id: str, enabled: bool):
        entry = self._registry.setdefault(ext_id, {})
        entry["intent_enabled"] = bool(enabled)
        _save_registry(self._data_dir, self._registry)

    # ── Qt extension iteration ─────────────────
    def _infos(self) -> list:
        return list(self._manager.extensions())

    def _info_by_id(self, ext_id: str):
        for ext in self._infos():
            if ext.id() == ext_id:
                return ext
        return None

    def _info_to_meta(self, ext: object) -> dict:
        return {
            "id": ext.id(),
            "name": ext.name(),
            "description": ext.description(),
            "version": self._manifest_version(ext.path()),
            "enabled": bool(ext.isEnabled()),
            "backend": self.name,
            "_path": ext.path() or "",
            "_installed_at": self._registry.get(ext.id(), {}).get("installed_at"),
        }

    @staticmethod
    def _manifest_version(path: str) -> str:
        try:
            with open(os.path.join(path, "manifest.json"), "r", encoding="utf-8") as f:
                return json.load(f).get("version", "?")
        except Exception:
            return "?"

    # ── Public API ─────────────────────────────
    def list_extensions(self) -> list:
        """Installed (user) extensions only — hides built-in ones."""
        out = []
        for ext in self._infos():
            if not ext.isInstalled():
                continue
            out.append(self._info_to_meta(ext))
        out.sort(key=lambda m: m.get("name", "").lower())
        return out

    def get_extension(self, ext_id: str) -> dict | None:
        ext = self._info_by_id(ext_id)
        return self._info_to_meta(ext) if ext is not None else None

    def is_enabled(self, ext_id: str) -> bool:
        ext = self._info_by_id(ext_id)
        return bool(ext.isEnabled()) if ext is not None else False

    def install_from_dir(self, source_dir: str) -> dict | None:
        if os.path.isdir(source_dir):
            manifest_path = os.path.join(source_dir, "manifest.json")
            if not os.path.isfile(manifest_path):
                raise ValueError("No manifest.json found in source directory")
        elif os.path.isfile(source_dir):
            # .crx / .zip — let Qt's installer validate the archive.
            pass
        else:
            raise ValueError("Extension source not found")
        self._manager.installExtension(source_dir)
        name = os.path.basename(os.path.normpath(source_dir))
        return {"id": None, "name": name, "version": "", "pending": True}

    def remove(self, ext_id: str) -> bool:
        ext = self._info_by_id(ext_id)
        if ext is None:
            return False
        self._manager.uninstallExtension(ext)
        return True

    def set_enabled(self, ext_id: str, enabled: bool) -> bool:
        ext = self._info_by_id(ext_id)
        if ext is None:
            return False
        self._manager.setExtensionEnabled(ext, bool(enabled))
        self._set_intent(ext_id, enabled)
        return True

    def install_all_enabled(self):
        """Re-apply persisted enabled intents after Qt auto-loads extensions.

        Qt loads installed extensions at startup in the disabled state, so we
        re-enable what the user turned on (idempotent if Qt persisted it).
        Since loading is asynchronous we also re-apply on every loadFinished.
        """
        self._apply_intents()

    # ── Async plumbing ─────────────────────────
    def _apply_intents(self):
        for ext in self._infos():
            if not ext.isInstalled():
                continue
            eid = ext.id()
            if eid in self._intent_applied:
                continue
            want = self._intent(eid)
            if bool(ext.isEnabled()) != want:
                self._manager.setExtensionEnabled(ext, want)
            self._intent_applied.add(eid)

    def _on_load_finished(self, extension):
        self._apply_intents()
        self._notify()

    def _on_install_finished(self, extension):
        if extension.isInstalled():
            eid = extension.id()
            entry = self._registry.setdefault(eid, {})
            entry["installed_at"] = time.time()
            entry.setdefault("intent_enabled", True)
            _save_registry(self._data_dir, self._registry)
            if not extension.isEnabled():
                self._manager.setExtensionEnabled(extension, True)
        else:
            self._last_error = extension.error() or "Extension install failed."
        self._notify()

    def _on_uninstall_finished(self, extension):
        self._registry.pop(extension.id(), None)
        self._intent_applied.discard(extension.id())
        _save_registry(self._data_dir, self._registry)
        self._notify()

    def take_last_error(self) -> str | None:
        err, self._last_error = self._last_error, None
        return err


# ─────────────────────────────────────────────
#  CONTENT-SCRIPT BACKEND (QtWebEngine < 6.10)
# ─────────────────────────────────────────────
class ContentScriptBackend(ExtensionBackend):
    """Installs, tracks, and injects content-script extensions."""

    name: str = "content-script"

    def __init__(self, data_dir: str, profile, notify=None):
        self._data_dir = data_dir
        self._profile = profile
        self._notify = notify or (lambda: None)
        self._root = _extensions_root(data_dir)
        self._registry = _load_registry(data_dir)
        self._injected: set = set()   # ids currently active on the profile

    @staticmethod
    def available() -> bool:
        return True

    # ── Registry access ─────────────────────
    def _ext_dir(self, ext_id: str) -> str:
        return os.path.join(self._root, ext_id)

    def list_extensions(self) -> list:
        """Return list of installed extension metas (from disk manifests)."""
        out = []
        for ext_id in os.listdir(self._root):
            ext_dir = self._ext_dir(ext_id)
            manifest_path = os.path.join(ext_dir, "manifest.json")
            if not os.path.isfile(manifest_path):
                continue
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                if not isinstance(meta, dict) or "id" not in meta:
                    continue
                meta.setdefault("enabled", bool(self._registry.get(ext_id, {}).get("enabled", True)))
                meta["_installed_at"] = self._registry.get(ext_id, {}).get("installed_at")
                out.append(meta)
            except Exception:
                continue
        out.sort(key=lambda m: m.get("name", "").lower())
        return out

    def get_extension(self, ext_id: str) -> dict | None:
        for m in self.list_extensions():
            if m.get("id") == ext_id:
                return m
        return None

    def is_enabled(self, ext_id: str) -> bool:
        entry = self._registry.get(ext_id)
        if entry is None:
            return True
        return bool(entry.get("enabled", True))

    # ── Install / remove ────────────────────
    def install_from_dir(self, source_dir: str) -> dict | None:
        """Copy an unpacked extension directory into the managed store.

        Returns the new extension meta on success, None on failure.
        """
        manifest_path = os.path.join(source_dir, "manifest.json")
        if not os.path.isfile(manifest_path):
            raise ValueError("No manifest.json found in source directory")

        with open(manifest_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        if not isinstance(meta, dict):
            raise ValueError("manifest.json is not an object")

        ext_id = meta.get("id") or _generate_id(meta.get("name", "extension"))
        meta["id"] = ext_id
        meta.setdefault("name", ext_id)
        meta.setdefault("version", "0.0.0")
        meta.setdefault("description", "")
        meta.setdefault("content_scripts", [])

        target = self._ext_dir(ext_id)
        # If reinstalling over an existing id, wipe the old copy.
        if os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(source_dir, target)

        # Write the normalized manifest (with generated id) back to disk so
        # list_extensions() and get_extension() can find it on reload.
        with open(os.path.join(target, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        # Persist enabled state (default enabled unless previously disabled).
        enabled = self._registry.get(ext_id, {}).get("enabled", True)
        self._registry[ext_id] = {
            "enabled": enabled,
            "installed_at": os.path.getmtime(manifest_path),
        }
        _save_registry(self._data_dir, self._registry)

        meta["enabled"] = enabled
        if enabled:
            self._inject(meta)
        return meta

    def remove(self, ext_id: str) -> bool:
        """Uninstall an extension: remove its scripts, folder, registry entry."""
        self._uneject(ext_id)
        target = self._ext_dir(ext_id)
        if os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)
        self._registry.pop(ext_id, None)
        _save_registry(self._data_dir, self._registry)
        return True

    # ── Enable / disable ────────────────────
    def set_enabled(self, ext_id: str, enabled: bool) -> bool:
        meta = self.get_extension(ext_id)
        if meta is None:
            return False
        entry = self._registry.setdefault(ext_id, {})
        entry["enabled"] = bool(enabled)
        _save_registry(self._data_dir, self._registry)
        if enabled:
            self._inject(meta)
        else:
            self._uneject(ext_id)
        return True

    # ── Script injection plumbing ───────────
    def install_all_enabled(self):
        """(Re)install every enabled extension's scripts onto the profile."""
        for meta in self.list_extensions():
            if self.is_enabled(meta["id"]):
                self._inject(meta, replace=True)

    def _inject(self, meta: dict, replace: bool = False):
        ext_id = meta["id"]
        ext_dir = self._ext_dir(ext_id)
        scripts = self._profile.scripts()

        if replace:
            self._uneject(ext_id)

        idx = 0
        for rule in meta.get("content_scripts", []):
            matches = rule.get("matches") or ["*://*/*"]
            injection_point = (
                QWebEngineScript.InjectionPoint.DocumentStart
                if rule.get("run_at") == "document_start"
                else QWebEngineScript.InjectionPoint.DocumentReady
            )
            for js_rel in rule.get("js", []):
                js_path = os.path.normpath(os.path.join(ext_dir, js_rel))
                if not os.path.isfile(js_path):
                    continue
                with open(js_path, "r", encoding="utf-8") as f:
                    source = f.read()

                # Each (id, rule, script) gets a unique name so we can remove
                # them individually during disable / reinstall.
                name = f"ns_ext_{ext_id}_{idx}"
                idx += 1

                script = QWebEngineScript()
                script.setName(name)
                # Isolated world keeps extension code from clobbering page JS.
                script.setWorldId(QWebEngineScript.ScriptWorldId.ContentWorld)
                script.setInjectionPoint(injection_point)
                script.setRunsOnSubFrames(bool(rule.get("all_frames", False)))
                script.setSourceCode(
                    "(function(){\n"
                    f"var MATCHES={json.dumps(matches)};\n"
                    "if(!(function(){try{var u=new URL(location.href);"
                    "for(var i=0;i<MATCHES.length;i++){var p=MATCHES[i];"
                    "if(p==='*://*/*')return true;"
                    "var ps=p.split('://');if(ps.length!==2)continue;"
                    "var sc=ps[0],rest=ps[1],host,path='/';"
                    "var slash=rest.indexOf('/');"
                    "if(slash>=0){host=rest.slice(0,slash);path=rest.slice(slash);}else{host=rest;}"
                    "if(sc!=='*'&&sc!==u.protocol.replace(':',''))continue;"
                    "if(host.indexOf('*')>=0){if(!(u.hostname.length>=host.length&&u.hostname.slice(u.hostname.length-host.length+1)===host.slice(1)))continue;"
                    "}else if(u.hostname!==host){continue;}"
                    "if(path==='*')return true;"
                    "var rx=new RegExp('^'+path.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&').replace(/\\\\\\*/g,'.*')+'$');"
                    "if(rx.test(u.pathname))return true;}"
                    "return false;}catch(e){return false}})())return;\n"
                    + source +
                    "\n})();\n"
                )

                # Remove this exact name in case of partial reinstall.
                for s in scripts.findChildren(name):
                    scripts.remove(s)
                scripts.insert(script)

        self._injected.add(ext_id)

    def _uneject(self, ext_id: str):
        """Remove all scripts owned by an extension id from the profile."""
        scripts = self._profile.scripts()
        prefix = f"ns_ext_{ext_id}_"
        for s in scripts.toList():
            if s.name().startswith(prefix):
                scripts.remove(s)
        self._injected.discard(ext_id)


# ─────────────────────────────────────────────
#  FACADE — selects the best available backend
# ─────────────────────────────────────────────
class ExtensionManager(QObject):
    """Public entry point for extension management.

    Wraps whichever backend can run on the installed Qt.  All operations
    delegate to ``self.backend``; callers never touch backends directly,
    which keeps the UI compatible across backends.

    ``changed`` fires whenever an install / enable / disable / remove
    finishes (synchronously or asynchronously), so the UI can refresh the
    management page.  ``take_last_error()`` surfaces async failures (e.g. a
    rejected .crx install).
    """

    changed = pyqtSignal()

    def __init__(self, data_dir: str, profile):
        super().__init__()
        self._data_dir = data_dir
        self._profile = profile
        self.backend: ExtensionBackend = self._make_backend()

    def _make_backend(self) -> ExtensionBackend:
        if NativeBackend.available():
            return NativeBackend(self._data_dir, self._profile, notify=self.changed.emit)
        return ContentScriptBackend(self._data_dir, self._profile, notify=self.changed.emit)

    def list_extensions(self) -> list:
        return self.backend.list_extensions()

    def get_extension(self, ext_id: str) -> dict | None:
        return self.backend.get_extension(ext_id)

    def is_enabled(self, ext_id: str) -> bool:
        return self.backend.is_enabled(ext_id)

    def install_from_dir(self, source_dir: str) -> dict | None:
        res = self.backend.install_from_dir(source_dir)
        self.changed.emit()
        return res

    def remove(self, ext_id: str) -> bool:
        res = self.backend.remove(ext_id)
        self.changed.emit()
        return res

    def set_enabled(self, ext_id: str, enabled: bool) -> bool:
        res = self.backend.set_enabled(ext_id, enabled)
        self.changed.emit()
        return res

    def install_all_enabled(self):
        self.backend.install_all_enabled()

    def take_last_error(self) -> str | None:
        return self.backend.take_last_error()