# Madeira AltStore Source (Unofficial)

An unofficial AltStore Classic source for [Madeira](https://github.com/willfaust/Madeira). Downloads link directly to official GitHub release IPAs; no rehosting or modifications.

**To install:** Add `https://YOUR-USERNAME.github.io/madeira-altstore-source/source.json` to AltStore Classic sources (replace YOUR-USERNAME).

The [GitHub Actions workflow](.github/workflows/update.yml) checks every six hours and generates the source metadata from the newest IPA. Run the workflow manually once after creating the repository. Enable GitHub Pages via **Settings → Pages → Deploy from a branch → main → / (root)**.

**Note:** The source's icon currently uses the developer's GitHub profile image, not Madeira's app icon. The workflow requires macOS to inspect embedded signing entitlements; failures stop publishing rather than inventing permission metadata. On a fresh setup, only the latest release is indexed; older releases accumulate as new versions arrive.
