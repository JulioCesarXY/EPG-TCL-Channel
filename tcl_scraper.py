import logging
import re
import traceback
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# --- Configurações de Ambiente ---
GEO_COUNTRY = 'US'
GEO_STATE = 'OH'
CLIENT_ID = '1776786148042-4c4uc'
API_GATEWAY = "https://gateway-prod.ideonow.com"
CDN_IMAGES = "https://tcl-channel-cdn.ideonow.com"
WEB_ORIGIN = "https://tcltv.plus"
EPG_OUTPUT_URL = "https://raw.githubusercontent.com/JulioCesarXY/EPG-TCL-Channel/refs/heads/main/tcl_epg.xml"

# --- Sistema de Rastreamento (Logs) ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
sys_logger = logging.getLogger("TCL_Scraper")

# --- Expressões Regulares para Tratamento de Títulos ---
RE_SEASON_COLON = re.compile(r'^(.+?)\s+S(\d+):\s+(.+)$', re.IGNORECASE)
RE_CLEAN_CODES = re.compile(r'\s+\d+$')
RE_SEASON_EPISODE = re.compile(r'^(.+?)\s+S(\d+)(?:\s+E(\d+))?(?:\s*[-–]\s*"?(.+?)"?\s*)?$', re.IGNORECASE)
RE_DASH_SPLIT = re.compile(r'^(.+?)\s{1,2}-\s+(.+)$')

def extract_meta_from_title(raw_title, default_season, default_episode):
    if not raw_title: 
        return raw_title, default_season, default_episode, None
    clean_str = raw_title.strip()
    
    match = RE_SEASON_COLON.match(clean_str)
    if match:
        return match.group(1).strip(), int(match.group(2)), default_episode, RE_CLEAN_CODES.sub('', match.group(3)).strip() or None
        
    match = RE_SEASON_EPISODE.match(clean_str)
    if match:
        return (match.group(1).strip(), 
                int(match.group(2)) if match.group(2) else default_season,
                int(match.group(3)) if match.group(3) else default_episode,
                match.group(4).strip().strip('"') if match.group(4) else None)
                
    if default_season is None and default_episode is None:
        match = RE_DASH_SPLIT.match(clean_str)
        if match: 
            return match.group(1).strip(), None, None, match.group(2).strip() or None
            
    return clean_str, default_season, default_episode, None


class TCLChannelsScraper:
    def __init__(self):
        self.session = requests.Session()
        self.configure_session()
        self.channels_registry = {}
        self.program_stubs = []
        self.details_registry = {}

    def configure_session(self):
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Origin": WEB_ORIGIN,
            "Referer": f"{WEB_ORIGIN}/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        })

    @property
    def payload_credentials(self):
        return {
            "userId": CLIENT_ID, "device_type": "web", "device_model": "web",
            "device_id": CLIENT_ID, "app_version": "1.0",
            "country_code": GEO_COUNTRY, "state_code": GEO_STATE,
        }

    def AuthorizeStreamUrl(self, bundle_id, source, fallback_url):
        payload = {"type": "channel", "bundle_id": bundle_id, "device_id": CLIENT_ID, "source": source, "stream_url": fallback_url}
        query_params = {"country_code": GEO_COUNTRY, "app_version": "3.2.7"}
        try:
            response = self.session.post(f"{API_GATEWAY}/api/metadata/v1/format-stream-url", params=query_params, json=payload, timeout=15)
            return response.json().get("stream_url") or fallback_url
        except:
            return fallback_url

    def parse_iso_time(self, iso_string):
        try:
            dt = datetime.strptime(iso_string, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            return dt.strftime("%Y%m%d%H%M%S +0000")
        except:
            return iso_string.replace("-", "").replace("T", "").replace(":", "").replace("Z", " +0000")

    def execute_scraping(self):
        sys_logger.info("=== Iniciando Motor de Raspagem Otimizado ===")
        
        livetab_data = self.session.get(f"{API_GATEWAY}/api/metadata/v2/livetab", params=self.payload_credentials).json()
        
        current_time = datetime.now(timezone.utc)
        time_filters = {
            "start": (current_time - timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": (current_time + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"), # Reduzido para 24h para acelerar no mobile
        }

        for entry in livetab_data.get("lines", []):
            category_id = entry["id"]
            category_title = entry.get("name", "General")
            sys_logger.info(f"Mapeando categoria: {category_title}")
            
            request_params = self.payload_credentials.copy()
            request_params.update({"category_id": category_id, **time_filters})
            
            try:
                epg_response = self.session.get(f"{API_GATEWAY}/api/metadata/v1/epg/programlist/by/category", params=request_params, timeout=20).json()
                
                for channel in epg_response.get("channels", []):
                    b_id = str(channel.get("bundle_id") or channel.get("id"))
                    
                    if b_id not in self.channels_registry:
                        authenticated_link = self.AuthorizeStreamUrl(b_id, channel.get("source"), channel.get("media", ""))
                        
                        self.channels_registry[b_id] = {
                            "id": b_id,
                            "name": channel.get("name"),
                            "logo": f"{CDN_IMAGES}{channel.get('logo_color')}" if channel.get('logo_color') else "",
                            "stream": authenticated_link,
                            "category": category_title,
                            "description": channel.get("description", "").strip()
                        }
                    
                    for program in channel.get("programs", []):
                        if program.get("id"):
                            self.program_stubs.append((b_id, program))
            except Exception as error:
                sys_logger.warning(f"Falha na categoria [{category_title}]: {error}")

        # Processamento de lote corrigido (Apenas IDs únicos reais, reduzindo em 90% a carga)
        if self.program_stubs:
            computed_ids = list(set(str(prog_data.get("id")) for _, prog_data in self.program_stubs if prog_data.get("id")))
            sys_logger.info(f"Coletando metadados de {len(computed_ids)} programas únicos...")

            chunk_size = 50
            total_chunks = (len(computed_ids) + chunk_size - 1) // chunk_size
            
            for index in range(0, len(computed_ids), chunk_size):
                chunk = computed_ids[index:index + chunk_size]
                batch_params = self.payload_credentials.copy()
                batch_params["ids"] = ",".join(chunk)

                try:
                    details_response = self.session.get(f"{API_GATEWAY}/api/metadata/v1/epg/program/detail", params=batch_params, timeout=20).json()

                    records_processed = details_response if isinstance(details_response, list) else [details_response] if isinstance(details_response, dict) else []

                    for detail_node in records_processed:
                        if isinstance(detail_node, dict) and "id" in detail_node:
                            d_id = str(detail_node["id"])
                            self.details_registry[d_id] = detail_node

                    sys_logger.info(f"  → Progresso Lotes: {index//chunk_size + 1} de {total_chunks}")
                except Exception as error:
                    sys_logger.warning(f"Falha no lote {index//chunk_size + 1}: {error}")

        sys_logger.info(f"Mapeamento concluído: {len(self.channels_registry)} canais.")
        return self.channels_registry, self.program_stubs, self.details_registry

    def compile_output_files(self):
        if not self.channels_registry:
            sys_logger.error("Sem dados para exportar.")
            return

        sys_logger.info("Escrevendo arquivos m3u8 e xml...")

        # M3U8
        with open("tcl.m3u8", "w", encoding="utf-8") as playlist:
            playlist.write(f'#EXTM3U x-tvg-url="{EPG_OUTPUT_URL}"\n')
            for ch in self.channels_registry.values():
                playlist.write(f'#EXTINF:-1 tvg-id="{ch["id"]}" tvg-logo="{ch["logo"]}" group-title="{ch["category"]}",{ch["name"]}\n')
                playlist.write(f'{ch["stream"]}\n')

        # XMLTV EPG
        xml_root = ET.Element("tv")
        for ch in self.channels_registry.values():
            channel_node = ET.SubElement(xml_root, "channel", id=ch["id"])
            ET.SubElement(channel_node, "display-name").text = ch["name"]
            if ch["logo"]:
                ET.SubElement(channel_node, "icon", src=ch["logo"])

        total_descriptions = 0
        
        for bundle_id, p_stub in self.program_stubs:
            p_id = str(p_stub.get("id")) if p_stub.get("id") else None
            matched_detail = self.details_registry.get(p_id) if p_id else None

            start_time_formatted = self.parse_iso_time(p_stub["start"])
            stop_time_formatted = self.parse_iso_time(p_stub["end"]) # BUG DA VARIÁVEL CORRIGIDO AQUI
            
            program_node = ET.SubElement(xml_root, "programme", start=start_time_formatted, stop=stop_time_formatted, channel=bundle_id)
            
            raw_title = p_stub.get("title", "No Title")
            clean_title, season, episode, subtitle = extract_meta_from_title(raw_title, p_stub.get("season"), p_stub.get("episode"))
            
            ET.SubElement(program_node, "title").text = clean_title
            if subtitle or p_stub.get("subtitle"):
                ET.SubElement(program_node, "sub-title").text = subtitle or p_stub.get("subtitle")
            
            resolved_desc = ""
            if matched_detail and isinstance(matched_detail.get("desc"), str) and matched_detail["desc"].strip():
                resolved_desc = matched_detail["desc"].strip()
            elif isinstance(p_stub.get("desc"), str) and p_stub["desc"].strip():
                resolved_desc = p_stub["desc"].strip()
            elif self.channels_registry.get(bundle_id, {}).get("description"):
                resolved_desc = self.channels_registry[bundle_id]["description"].strip()

            if resolved_desc:
                try:
                    ET.SubElement(program_node, "desc").text = resolved_desc
                    total_descriptions += 1
                except:
                    pass

            if season or episode:
                episode_tag = ET.SubElement(program_node, "episode-num", system="onscreen")
                episode_tag.text = f"S{season or 0:02d}E{episode or 0:02d}"
            
            assigned_rating = matched_detail.get("rating") if matched_detail else p_stub.get("rating", "TV-NR")
            rating_node = ET.SubElement(program_node, "rating", system="VCHIP")
            ET.SubElement(rating_node, "value").text = assigned_rating

        xml_tree = ET.ElementTree(xml_root)
        xml_tree.write("tcl_epg.xml", encoding="utf-8", xml_declaration=True)
        sys_logger.info(f"Arquivos salvos! Total de descrições processadas: {total_descriptions}")


if __name__ == "__main__":
    try:
        scraper = TCLChannelsScraper()
        scraper.execute_scraping()
        scraper.compile_output_files()
        sys_logger.info("=== Concluído com Sucesso! ===")
    except Exception as critical_error:
        sys_logger.error(f"Erro: {critical_error}")
        sys_logger.debug(traceback.format_exc())
