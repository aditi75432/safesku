from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "apps/api/app/demo_app.py"
HTML = ROOT / "apps/api/app/static/index.html"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Could not find expected {label} marker in {old[:80]!r}")
    return text.replace(old, new, 1)


def main() -> None:
    demo = DEMO.read_text(encoding="utf-8")
    import_marker = "from .workspace import WorkspaceService\n"
    if "from .local_bundle_upload import router as local_bundle_upload_router" not in demo:
        demo = replace_once(
            demo,
            import_marker,
            import_marker + "from .local_bundle_upload import router as local_bundle_upload_router\n",
            "demo_app import marker",
        )

    include_marker = "app = FastAPI(\n"
    # Add after FastAPI construction closes, immediately before legacy globals.
    install_marker = "store = DataStore()\n"
    if "app.include_router(local_bundle_upload_router)" not in demo:
        demo = replace_once(
            demo,
            install_marker,
            "app.include_router(local_bundle_upload_router)\n\n" + install_marker,
            "router installation marker",
        )
    DEMO.write_text(demo, encoding="utf-8")

    html = HTML.read_text(encoding="utf-8")
    old = """    const fd=new FormData();fd.append('file',file);\n    $('bundleStatus').textContent=`Uploading ${file.name} (${(file.size/1024/1024).toFixed(1)} MiB)…`;\n    const d=await api('/api/workspace/bundles/import',{method:'POST',body:fd});\n    const rows=d.bundle?.datasets||[];\n"""
    new = r"""    const started=await api('/api/workspace/bundles/upload/start',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({filename:file.name,size_bytes:file.size})
    });
    const chunkSize=Number(started.chunk_size||1048576);
    const totalChunks=Number(started.total_chunks||Math.ceil(file.size/chunkSize));
    const uploadId=started.upload_id;
    const toBase64=bytes=>{
      let binary='';
      const step=0x8000;
      for(let i=0;i<bytes.length;i+=step){binary+=String.fromCharCode(...bytes.subarray(i,Math.min(i+step,bytes.length)));}
      return btoa(binary);
    };
    for(let index=0;index<totalChunks;index++){
      const start=index*chunkSize;
      const end=Math.min(file.size,start+chunkSize);
      const bytes=new Uint8Array(await file.slice(start,end).arrayBuffer());
      await api('/api/workspace/bundles/upload/chunk',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({upload_id:uploadId,chunk_index:index,total_chunks:totalChunks,data:toBase64(bytes)})
      });
      const pct=Math.round((index+1)/totalChunks*100);
      $('bundleStatus').textContent=`Uploading ${file.name} · ${index+1}/${totalChunks} chunks · ${pct}%`;
    }
    $('bundleStatus').textContent='Upload complete. SafeSKU is validating the bundle…';
    const d=await api('/api/workspace/bundles/upload/complete',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({upload_id:uploadId,total_chunks:totalChunks})
    });
    const rows=d.bundle?.datasets||[];
"""
    html = replace_once(html, old, new, "local bundle upload block")
    html = html.replace(
        "Upload a CPSC dataset to enable the investigation pipeline.",
        "Upload a SafeSKU Bundle to enable the investigation pipeline.",
        1,
    )
    HTML.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
