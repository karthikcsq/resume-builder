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
    
    # Use placeholders for Unicode math symbols to preserve them through escaping
    import uuid
    placeholders = {}
    
    unicode_math_replacements = [
        ("≈", r"$\approx$"),
        ("±", r"$\pm$"),
        ("×", r"$\times$"),
        ("÷", r"$\div$"),
        ("≤", r"$\leq$"),
        ("≥", r"$\geq$"),
        ("≠", r"$\neq$"),
        ("∞", r"$\infty$"),
        ("∑", r"$\sum$"),
        ("∏", r"$\prod$"),
        ("√", r"$\sqrt{}$"),
        ("°", r"$^\circ$"),
    ]
    
    # Replace Unicode math with placeholders
    for char, latex_code in unicode_math_replacements:
        if char in text:
            placeholder = f"UNICODEMATH{uuid.uuid4().hex}"
            placeholders[placeholder] = latex_code
            text = text.replace(char, placeholder)
    
    # Handle typographic characters (no math mode needed)
    typography_replacements = [
        ("–", r"--"),  # en-dash
        ("—", r"---"), # em-dash
        (""", r"``"),  # left double quote
        (""", r"''"),  # right double quote
        ("'", r"`"),   # left single quote
        ("'", r"'"),   # right single quote
        ("…", r"..."), # ellipsis
    ]
    
    for char, replacement in typography_replacements:
        text = text.replace(char, replacement)
    
    # Then handle standard LaTeX special characters
    latex_special = [
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
    for char, replacement in latex_special:
        text = text.replace(char, replacement)
    
    # Restore math symbols from placeholders
    for placeholder, latex_code in placeholders.items():
        text = text.replace(placeholder, latex_code)
    
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



def load_yaml(yaml_path: str = "resume_truth.yaml"):
    """Load YAML data from the given path and return the parsed object."""
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

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


def render_target(template_name: str, out_tex: str, yaml_content: str, target: str | None = None):
    """Render a template from a YAML string and optionally build a PDF.

    Args:
        template_name: Jinja2 template filename under `templates/`.
        out_tex: Output .tex file path. The .tex and generated .pdf will reside
                 in the same directory as this path. No output/ folder is used.
        yaml_content: The YAML document as a string (UTF-8 text).
        target: Optional filter target (e.g., "cv" or "resume"). If provided,
                entries with show_on excluding this target are removed.
    """
    output = create_tex(template_name=template_name, yaml_content=yaml_content, target=target)

    # Ensure destination directory exists
    out_tex_path = Path(out_tex)
    out_dir = out_tex_path.parent if out_tex_path.parent != Path("") else Path(".")
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(out_tex_path, "w", encoding="utf-8") as f:
        f.write(output)
        
    print("Wrote LaTeX to", out_tex_path)

    # Run pdflatex if available
    if shutil.which("pdflatex"):
        try:
            # Run in the output directory to keep artifacts together
            subprocess.run(["pdflatex", out_tex_path.name], check=True, cwd=str(out_dir))
        except subprocess.CalledProcessError as e:
            print(f"pdflatex failed with exit code {e.returncode} for {out_tex_path}")
    else:
        print("pdflatex not found in PATH — skipping PDF generation step")
    # Return path to generated PDF for the caller to handle copying
    src_pdf = out_tex_path.with_suffix(".pdf")

    # Clean up auxiliary files produced by pdflatex
    try:
        cleanup_aux_files(str(out_tex_path))
    except Exception as e:
        print(f"Failed to cleanup auxiliary files for {out_tex_path}: {e}")

    # Return the path where the PDF would be (may not exist if pdflatex missing)
    return src_pdf


def create_tex(template_name: str, yaml_content: str, target: str | None = None) -> str:
    """Create and return the rendered LaTeX string for given YAML content.

    This function isolates the pure transformation (YAML -> filtered data -> escaped -> Jinja render)
    so callers that only need the LaTeX source (e.g., for previewing, diffing, or external compilation)
    can reuse logic without writing files or invoking pdflatex.

    Args:
        template_name: Jinja2 template filename under `templates/`.
        yaml_content: The YAML document as a UTF-8 string.
        target: Optional filter target (e.g., "cv" or "resume"). If provided, objects with a show_on
                list excluding this target are pruned.

    Returns:
        The fully rendered LaTeX document as a string.
    """
    tmpl = env.get_template(template_name)
    # Parse YAML
    try:
        data = yaml.safe_load(yaml_content) or {}
    except Exception as e:
        raise ValueError(f"Failed to parse YAML: {e}") from e

    data_to_render = data
    if target:
        try:
            data_to_render = filter_for_target(data, target)
        except Exception as e:
            raise ValueError(f"Filtering for target '{target}' failed: {e}") from e

    # Escape for LaTeX
    try:
        data_escaped = escape_all(data_to_render or {})
    except Exception as e:
        raise ValueError(f"Failed to escape data for LaTeX: {e}") from e

    try:
        rendered = tmpl.render(**data_escaped)
    except Exception as e:
        raise RuntimeError(f"Template render failed for '{template_name}': {e}") from e

    return rendered


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
    # Example usage: render both CV and resume using the default YAML file as input
    default_yaml_path = "resume_truth.yaml"
    try:
        with open(default_yaml_path, "r", encoding="utf-8") as _f:
            yaml_str = _f.read()
    except FileNotFoundError:
        print(f"Default YAML not found: {default_yaml_path}")
        yaml_str = "{}"

    render_target("cv.tex.j2", "cv_output.tex", yaml_str, target="cv")
    render_target("resume.tex.j2", "resume_output.tex", yaml_str, target="resume")