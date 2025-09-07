import uuid
from pathlib import Path
import shutil
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
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
        cv_generated = render_target("cv.tex.j2", "cv_output.tex", yaml_input.yaml_content, target="cv")
        resume_generated = render_target("resume.tex.j2", "resume_output.tex", yaml_input.yaml_content, target="resume")
    except Exception as e:
        return JSONResponse({"error": f"Rendering failed: {e}"}, status_code=500)

    # Copy PDFs into the per-request workdir for download endpoints
    cv_pdf = workdir / "cv_output.pdf"
    resume_pdf = workdir / "resume_output.pdf"

    try:
        if cv_generated and cv_generated.exists():
            shutil.copyfile(cv_generated, cv_pdf)
        if resume_generated and resume_generated.exists():
            shutil.copyfile(resume_generated, resume_pdf)
    except Exception as e:
        # Continue to existence check below; may fail if pdflatex wasn't available
        print(f"Failed to copy generated PDFs into workdir: {e}")

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
