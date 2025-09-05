import yaml
from jinja2 import Environment, FileSystemLoader
import subprocess
import os
import shutil
from pathlib import Path


def latex_escape(text: str) -> str:
    # Replace backslash first to avoid re-escaping backslashes introduced by
    # later replacements (e.g. replacing '&' with '\&' shouldn't then turn
    # the leading backslash into '\textbackslash{}'). Use an ordered list.
    replacements = [
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]
    for char, replacement in replacements:
        text = text.replace(char, replacement)
    return text

def escape_all(data):
    if isinstance(data, dict):
        return {k: escape_all(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [escape_all(v) for v in data]
    elif isinstance(data, str):
        return latex_escape(data)
    else:
        return data



# Load YAML
with open("resume_truth.yaml", "r") as f:
    data = yaml.safe_load(f)

# Jinja2 environment (looks for templates in ./templates)
env = Environment(
    loader=FileSystemLoader("templates"),
    # Use low-conflict delimiters to avoid clashes with LaTeX content
    block_start_string = '<%',
    block_end_string = '%>',
    variable_start_string = '<<<',
    variable_end_string = '>>>',
    comment_start_string = '<#',
    comment_end_string = '#>',
)
def filter_for_target(obj, target="cv"):
    """Recursively filter a loaded YAML structure.

    If an object is a dict and contains a `show_on` key, the object is
    dropped unless the `target` is present in that list. Lists are
    filtered item-by-item.
    """
    if isinstance(obj, dict):
        if "show_on" in obj:
            show = obj.get("show_on") or []
            # allow single-string show_on values
            if isinstance(show, str):
                show = [show]
            if target not in show:
                return None
        result = {}
        for k, v in obj.items():
            if k == "show_on":
                continue
            filtered = filter_for_target(v, target)
            if filtered is not None:
                result[k] = filtered
        return result
    elif isinstance(obj, list):
        out = []
        for item in obj:
            f = filter_for_target(item, target)
            if f is not None:
                out.append(f)
        return out
    else:
        return obj


def render_target(template_name: str, out_tex: str, target: str = None):
    """Render a template and optionally build PDF and copy to public folder.

    If `target` is provided, the YAML data is filtered with `filter_for_target`
    before escaping and rendering.
    """
    tmpl = env.get_template(template_name)

    data_to_render = data
    if target:
        data_to_render = filter_for_target(data, target)

    data_escaped = escape_all(data_to_render or {})
    output = tmpl.render(**data_escaped)

    with open(out_tex, "w", encoding="utf-8") as f:
        f.write(output)

    # Run pdflatex if available
    if shutil.which("pdflatex"):
        try:
            subprocess.run(["pdflatex", out_tex], check=True)
        except subprocess.CalledProcessError as e:
            print(f"pdflatex failed with exit code {e.returncode} for {out_tex}")
    else:
        print("pdflatex not found in PATH — skipping PDF generation step")
    # Return path to generated PDF for the caller to handle copying
    src_pdf = Path(out_tex).with_suffix(".pdf")
    # Clean up auxiliary files produced by pdflatex
    try:
        cleanup_aux_files(out_tex)
    except Exception as e:
        print(f"Failed to cleanup auxiliary files for {out_tex}: {e}")
    return src_pdf


def cleanup_aux_files(tex_path: str):
    """Remove common auxiliary files produced by pdflatex for the given tex file.

    Removes: .aux, .log, .out for the basename (e.g. cv_output.aux)
    """
    base = Path(tex_path).with_suffix("")
    for suffix in (".aux", ".log", ".out"):
        p = base.with_suffix(suffix)
        try:
            if p.exists():
                p.unlink()
                print(f"Removed {p}")
        except Exception as e:
            print(f"Could not remove {p}: {e}")

if __name__ == "__main__":
    # Example usage: render both CV and resume
    render_target("cv.tex.j2", "cv_output.tex", target="cv")
    render_target("resume.tex.j2", "resume_output.tex", target="resume")