# Resume Builder

Generate a clean Resume and CV from a single YAML file using Jinja2 + LaTeX.

## Prerequisites
- Python 3.10+
- pip packages: `pyyaml`, `jinja2`
- (Optional) A LaTeX distribution for PDF output (e.g., TeX Live or MiKTeX). If `pdflatex` is not in PATH, only the `.tex` files will be generated.

## Quick start
1. Edit your data in `resume_truth.yaml`.
2. Render both resume and CV variants by running the script.

### Windows (PowerShell)
```powershell
python -m pip install --upgrade pip ; pip install pyyaml jinja2
python .\render_tex.py
```

This will generate:
- Resume: `resume_output.tex` and (if LaTeX is installed) `resume_output.pdf`
- CV: `cv_output.tex` and (if LaTeX is installed) `cv_output.pdf`

## Run without installing LaTeX (Docker)
You can build a container image that includes TeX Live and Python deps, then render inside the container.

### Build the image
```powershell
docker build -t resume-builder .
```

### Render (outputs will appear in your workspace)
```powershell
# From the repository root
docker run --rm -v ${PWD}:/app -w /app resume-builder
```

This runs `python render_tex.py` inside the container and writes:
- `resume_output.tex` and `resume_output.pdf`
- `cv_output.tex` and `cv_output.pdf`

Notes:
- On some shells, use `-v ${PWD}:/app` (PowerShell) or `-v "$PWD":/app` (bash) to mount the current folder.
- The image uses a full TeX Live install for convenience; it’s large. You can slim it down later if needed.

## Editing your info
Open `resume_truth.yaml` and update fields like:
- `name`
- `contact` and `links`
- `education`, `experience`, `projects`, `skills`

Each item can include an optional `show_on` list to control where it appears:
- `show_on: ["resume", "cv"]` — show in both
- `show_on: ["resume"]` — show only in resume
- `show_on: ["cv"]` — show only in CV

## How rendering works
- The script loads `resume_truth.yaml` and escapes LaTeX-sensitive characters.
- It filters items by target: `resume` or `cv` using `show_on`.
- It renders with templates in `templates/`:
	- `templates/resume.tex.j2` -> `resume_output.tex`
	- `templates/cv.tex.j2` -> `cv_output.tex`
- If `pdflatex` is available, PDFs are built and aux files are cleaned up.

## Re-render only one target
You can import and call the renderer from Python to generate a single variant:

```python
from render_tex import render_target

# Resume only
render_target("resume.tex.j2", "resume_output.tex", target="resume")

# CV only
render_target("cv.tex.j2", "cv_output.tex", target="cv")
```

## Troubleshooting
- If PDFs aren’t created, ensure `pdflatex` is installed and in PATH; otherwise, open the `.tex` files with your LaTeX editor to compile.
- YAML must be valid — run it through a YAML linter if parsing errors occur.
- On Windows, if `python` doesn’t work, try `py -3` instead.

## License
See `LICENSE`.