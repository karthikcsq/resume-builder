# Build image that can render PDFs from templates without host LaTeX
# Using slim Python base + TeX Live
FROM python:3.12-slim

# Avoid interactive tzdata prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install a minimal TeX Live set needed by the templates
# Packages cover: hyperref, titlesec, enumitem, tcolorbox(+pgf), xcolor, geometry,
# tabularx, fullpage, fancyhdr, multicol, ragged2e, graphicx, lipsum, wrapfig, float,
# and fonts (cfr-lm, marvosym, fontawesome5)
RUN apt-get update \
       && apt-get install -y --no-install-recommends \
             make wget ca-certificates \
             ghostscript \
             latexmk \
             texlive-full \
       && rm -rf /var/lib/apt/lists/*

# Install Python deps
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Ensure output directory exists
RUN mkdir -p /app/output

# Copy project
COPY . .

CMD ["python", "render_tex.py"]
