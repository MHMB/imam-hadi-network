# Self-hosted fonts

Drop the following files into this directory:

- `Vazirmatn-Regular.woff2`
- `Vazirmatn-Bold.woff2`

Download from https://github.com/rastikerdar/vazirmatn/releases (latest).

P4 (Web Shell) verifies the font loads. Until then `next/font/local` falls
back to system fonts and the build still succeeds.
