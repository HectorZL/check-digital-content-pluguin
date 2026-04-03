from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Página de Configuración (Interfaz web)
@app.get("/", response_class=HTMLResponse)
async def config_page(request: Request):
    html_content = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Configurar Disponibilidad Digital</title>
        <style>
            body { font-family: sans-serif; background: #1a1a2e; color: #fff; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .container { background: #16213e; padding: 40px; border-radius: 10px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
            input { padding: 12px; width: 300px; border-radius: 5px; border: none; margin-bottom: 20px; font-size: 16px; }
            button { padding: 12px 24px; background: #8a5a19; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; font-weight: bold; transition: 0.3s; }
            button:hover { background: #a46d22; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Plugin de Stremio</h2>
            <p>Ingresa tu API Key de TMDB para instalar el add-on:</p>
            <input type="text" id="apikey" placeholder="Ej: a1b2c3d4e5f6g7h8..." required>
            <br>
            <button onclick="install()">Instalar en Stremio</button>
        </div>

        <script>
            function install() {
                const apiKey = document.getElementById('apikey').value.trim();
                if(!apiKey) { alert("Por favor ingresa tu API Key"); return; }
                
                // Obtenemos el dominio actual de Vercel
                const host = window.location.host;
                // Armamos el link de Stremio (stremio:// en vez de https://)
                const installUrl = "stremio://" + host + "/" + apiKey + "/manifest.json";
                window.location.href = installUrl;
            }
        </script>
    </body>
    </html>
    """
    return html_content

# 2. Manifest dinámico con la API Key en la ruta
@app.get("/{api_key}/manifest.json")
def get_manifest(api_key: str):
    return {
        "id": "com.disponibilidad.digital.global",
        "version": "1.0.0",
        "name": "Disponibilidad Digital",
        "description": "Verifica si el título está en digital (requiere TMDB API Key).",
        "resources": ["stream"],
        "types": ["movie", "series"],
        "catalogs": [],
        "behaviorHints": {
            "configurable": True,
            "configurationRequired": True
        }
    }

# 3. Endpoint que usa la API Key que el usuario guardó en la URL
@app.get("/{api_key}/stream/{type}/{imdb_id}.json")
async def get_stream(api_key: str, type: str, imdb_id: str):
    clean_imdb_id = imdb_id.split(":")[0]
    tmdb_type = "tv" if type == "series" else "movie"
    
    plataformas = await obtener_plataformas_tmdb(api_key, clean_imdb_id, tmdb_type)
    
    # Manejo de error si la API Key es incorrecta
    if plataformas is None:
         return {"streams": [{"name": "Error", "title": "API Key de TMDB inválida"}]}
    
    if plataformas:
        texto_plataformas = ", ".join(plataformas[:10])
        if len(plataformas) > 10:
            texto_plataformas += " y más..."
            
        return {
            "streams": [
                {
                    "name": "OK",
                    "title": f"Disponible en digital:\n{texto_plataformas}",
                    "externalUrl": f"https://www.themoviedb.org/{tmdb_type}/{clean_imdb_id}" 
                }
            ]
        }
    
    return {"streams": []}

async def obtener_plataformas_tmdb(api_key: str, imdb_id: str, tmdb_type: str):
    async with httpx.AsyncClient() as client:
        try:
            # 1. Obtener el TMDB ID validando la API Key
            find_url = f"https://api.themoviedb.org/3/find/{imdb_id}?api_key={api_key}&external_source=imdb_id"
            res_find = await client.get(find_url)
            
            if res_find.status_code != 200:
                return None  # Key inválida o límite de peticiones
                
            data_find = res_find.json()
            resultados = data_find.get(f"{tmdb_type}_results", [])
            
            if not resultados:
                return []
                
            tmdb_id = resultados[0]["id"]

            # 2. Consultar proveedores mundiales
            prov_url = f"https://api.themoviedb.org/3/{tmdb_type}/{tmdb_id}/watch/providers?api_key={api_key}"
            res_prov = await client.get(prov_url)
            prov_data = res_prov.json()
            
            paises_data = prov_data.get("results", {})
            disponibles = set()
            
            for pais_info in paises_data.values():
                for categoria in ["flatrate", "rent", "buy"]:
                    if categoria in pais_info:
                        for proveedor in pais_info[categoria]:
                            disponibles.add(proveedor["provider_name"])
                            
            return sorted(list(disponibles))
        except Exception:
            return None
