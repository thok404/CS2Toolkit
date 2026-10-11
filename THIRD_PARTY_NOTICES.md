## Third-Party Notices

This document provides a high-level summary of key third-party dependencies used by this project.

It is informational only and does not replace the original license texts published by each upstream project.
When distributing source code or binary releases, you should review the exact dependency versions you ship and preserve all required notices.

### Project License

- `CS2Toolkit`: `GPL-3.0-only`
- While this project continues to depend on `PySide6-Fluent-Widgets` and no separate commercial license for that dependency has been obtained, public distribution should be understood as following the `GPLv3` path rather than a custom license path that adds restrictions such as "no modification", "no redistribution", or "no paid redistribution".

### Runtime Dependencies

- `PySide6`
  - Upstream: Qt for Python
  - License summary: open source distribution is available under `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`
  - Notes: `PySide6` itself can be used for commercial distribution under its own licensing terms, but that does not automatically make the whole application safe for closed-source commercial use if other dependencies impose stricter terms.

- `PySide6-Fluent-Widgets`
  - Upstream: `zhiyiYo / atiasn`
  - License summary: upstream project states `GPLv3` for non-commercial/open-source usage and offers a separate commercial license
  - Notes: this dependency is the key licensing constraint in this project. If you publish this project as `GPLv3` open source, this dependency is generally aligned with that model. If you want to distribute a closed-source or otherwise separately commercial version, or you want to impose extra restrictions that conflict with `GPLv3`, you should obtain a commercial license from the library author or remove the dependency and re-evaluate the licensing position of the whole project.

- `requests`
  - Upstream: Python Software Foundation ecosystem
  - License summary: `Apache-2.0`

- `pycaw`
  - Upstream: AndreMiras
  - License summary: `MIT`

- `zstandard`
  - Upstream: Gregory Szorc
  - License summary: upstream repository declares `BSD-3-Clause`

- `Pillow`
  - Upstream: https://github.com/python-pillow/Pillow
  - License: `MIT-CMU`
  - Used for AVIF decoding, image orientation and alpha preservation. Preserve Pillow's bundled license and codec dependency notices when distributing binaries.

### Platform and External Interfaces

- `Steam` registry and installation path detection are used only for local discovery of the user's game installation.
- `Counter-Strike 2` Game State Integration (`GSI`) is used as an external local interface exposed by the game.
- `Valve`, `Counter-Strike`, `Counter-Strike 2`, and related names, logos, and assets are not part of this project's license grant.

### Distribution Guidance

- Under `GPLv3`, third parties may modify, redistribute, and even charge money for distributing the code, provided they continue to comply with `GPLv3`.
- In other words, `GPLv3` can constrain closed-source redistribution, but it does not prevent redistribution or paid redistribution when the distributor still fulfills the GPL obligations.
- Do not assume third-party media files are redistributable just because the code can load them.
- Do not bundle game assets, anime/game artwork, sound packs, fonts, or user-imported resources unless you have explicit permission to redistribute them.
- For this specific project, evaluate licensing at the dependency set level, not at the `PySide6` level alone. `PySide6-Fluent-Widgets` materially affects commercial distribution options.
- Project name, icons, logos, screenshots, sponsorship QR images, default promotional assets, and other non-code materials that are not explicitly relicensed should not be assumed to be part of the `GPLv3` code grant.
- Forks or redistributions should not imply official affiliation with the original author, and should not continue using the original branding, author identity, or sponsorship assets without permission.
- If you ship binary releases, include:
  - the project `LICENSE`
  - this `THIRD_PARTY_NOTICES.md`
  - any additional notices required by the exact versions of bundled dependencies

### Verification Sources

Before a public release, re-check the upstream license pages for the exact versions you use:

- `PySide6`: PyPI / Qt for Python documentation
- `PySide6-Fluent-Widgets`: upstream GitHub / PyPI page
- `requests`: PyPI / upstream GitHub license
- `pycaw`: upstream GitHub license
- `zstandard`: PyPI / upstream GitHub license
