import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Permitir todas las conexiones (CORS) para evitar bloqueos
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir archivos estáticos si existe la carpeta
if os.path.exists("assets"):
    app.mount("/assets", StaticFiles(directory="assets"), name="assets")

# Esta es la ruta principal mejorada
@app.get("/")
@app.head("/")  # <--- ESTO arregla el error 405 de Render
async def root():
    return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    # Render usa PORT, si no existe usamos 10000
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)