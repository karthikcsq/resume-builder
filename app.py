import uuid
from pathlib import Path
import shutil
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel
from render_tex import render_target
import yaml

app = FastAPI()

TMP_ROOT = Path("/app/tmp")
TMP_ROOT.mkdir(parents=True, exist_ok=True)

class YamlInput(BaseModel):
    yaml_content: str

@app.post("/render")
async def render(yaml_input: YamlInput):
    # Make a unique directory for this request
    request_id = str(uuid.uuid4())
    workdir = TMP_ROOT / request_id
    workdir.mkdir(parents=True, exist_ok=True)

    # Call renderer directly with YAML string
    try:
        cv_generated = render_target(
            "cv.tex.j2", str(workdir / "cv_output.tex"), yaml_input.yaml_content, target="cv"
        )
        resume_generated = render_target(
            "resume.tex.j2", str(workdir / "resume_output.tex"), yaml_input.yaml_content, target="resume"
        )
    except Exception as e:
        return JSONResponse({"error": f"Rendering failed: {e}"}, status_code=500)

    # PDFs should already be generated directly in the per-request workdir
    cv_pdf = Path(cv_generated) if cv_generated else (workdir / "cv_output.pdf")
    resume_pdf = Path(resume_generated) if resume_generated else (workdir / "resume_output.pdf")

    if not cv_pdf.exists() and not resume_pdf.exists():
        return JSONResponse({"error": "No PDFs generated (is pdflatex installed?)"}, status_code=500)

    # Return download links
    return {
        "request_id": request_id,
        "cv_pdf": f"/download/{request_id}/cv",
        "resume_pdf": f"/download/{request_id}/resume",
    }

@app.get("/download/{request_id}/{doc_type}")
async def download_pdf(request_id: str, doc_type: str):
    workdir = TMP_ROOT / request_id
    if not workdir.exists():
        return JSONResponse({"error": "Invalid request ID"}, status_code=404)

    if doc_type == "cv":
        pdf_path = workdir / "cv_output.pdf"
    elif doc_type == "resume":
        pdf_path = workdir / "resume_output.pdf"
    else:
        return JSONResponse({"error": "Invalid doc type"}, status_code=400)

    if not pdf_path.exists():
        return JSONResponse({"error": "PDF not found"}, status_code=404)

    return FileResponse(pdf_path, media_type="application/pdf", filename=pdf_path.name)


class JsonInput(BaseModel):
    data: dict

@app.post("/render_json")
async def render_json(json_input: JsonInput):
    """Accept JSON, convert to YAML string, then render resume and CV."""
    # Convert JSON to YAML string (preserve order, allow unicode)
    try:
        yaml_str = yaml.safe_dump(json_input.data, sort_keys=False, allow_unicode=True)
    except Exception as e:
        return JSONResponse({"error": f"Failed to convert JSON to YAML: {e}"}, status_code=400)

    # Reuse the /render logic by constructing YamlInput
    return await render(YamlInput(yaml_content=yaml_str))


@app.post("/render_json_pdf")
async def render_json_pdf(json_input: JsonInput, doc_type: str = "resume"):
    """Accept JSON and return a single PDF (resume or cv) directly.

    Query/body parameter:
    - doc_type: "resume" or "cv" (default: "resume").

    This endpoint renders, streams the PDF back to the client, and cleans up
    any temporary directories and generated files used during the process.
    """
    # Validate doc_type
    if doc_type not in ("resume", "cv"):
        return JSONResponse({"error": "Invalid doc_type. Use 'resume' or 'cv'."}, status_code=400)

    # Convert incoming JSON data to YAML string
    try:
        yaml_str = yaml.safe_dump(json_input.data, sort_keys=False, allow_unicode=True)
    except Exception as e:
        return JSONResponse({"error": f"Failed to convert JSON to YAML: {e}"}, status_code=400)

    # Create a per-request working directory
    request_id = str(uuid.uuid4())
    workdir = TMP_ROOT / request_id
    workdir.mkdir(parents=True, exist_ok=True)

    # Choose template and filenames based on doc_type
    if doc_type == "cv":
        template_name = "cv.tex.j2"
        out_tex_name = "cv_output.tex"
        download_name = "cv_output.pdf"
        target = "cv"
    else:
        template_name = "resume.tex.j2"
        out_tex_name = "resume_output.tex"
        download_name = "resume_output.pdf"
        target = "resume"

    out_tex_path = workdir / out_tex_name

    pdf_path = None
    pdf_bytes = None
    try:
        # Render and build PDF via existing renderer, outputting into workdir
        generated_pdf_path = render_target(template_name, str(out_tex_path), yaml_str, target=target)

        # Ensure a PDF exists
        if not generated_pdf_path or not Path(generated_pdf_path).exists():
            return JSONResponse({"error": "No PDF generated (is pdflatex installed?)"}, status_code=500)

        pdf_path = Path(generated_pdf_path)

        # Read bytes so we can clean up files immediately after
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

    except Exception as e:
        return JSONResponse({"error": f"Rendering failed: {e}"}, status_code=500)
    finally:
        # Attempt cleanup: delete files in workdir and remove the directory
        try:
            # Remove generated PDF if present
            if pdf_path and Path(pdf_path).exists():
                try:
                    Path(pdf_path).unlink()
                except Exception as _e:
                    print(f"Cleanup warning: could not delete PDF {pdf_path}: {_e}")

            # Remove the generated TEX file in workdir
            try:
                if out_tex_path.exists():
                    out_tex_path.unlink()
            except Exception as _e:
                print(f"Cleanup warning: could not delete TEX {out_tex_path}: {_e}")

            # Remove working directory tree
            try:
                if workdir.exists():
                    shutil.rmtree(workdir, ignore_errors=True)
            except Exception as _e:
                print(f"Cleanup warning: could not remove workdir {workdir}: {_e}")
        except Exception as _e:
            print(f"General cleanup warning: {_e}")

    # If we couldn't read the PDF for some reason
    if not pdf_bytes:
        return JSONResponse({"error": "Failed to read generated PDF"}, status_code=500)

    # Stream the file back as an attachment
    headers = {
        "Content-Type": "application/pdf",
        "Content-Disposition": f"attachment; filename={download_name}",
        "Cache-Control": "no-store",
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
