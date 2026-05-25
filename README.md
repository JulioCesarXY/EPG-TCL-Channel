# 📺 EPG-TCL-Channel

<p align="center">
  <img src="https://img.shields.io/github/actions/workflow/status/JulioCesarXY/EPG-TCL-Channel/tcl_update.yml?branch=main&style=for-the-badge&logo=githubactions&logoColor=white&label=Automa%C3%A7%C3%A3o" alt="GitHub Actions Status">
  <img src="https://img.shields.io/github/last-commit/JulioCesarXY/EPG-TCL-Channel?style=for-the-badge&color=blue&label=Última%20Atualização" alt="Last Commit">
  <img src="https://img.shields.io/github/license/JulioCesarXY/EPG-TCL-Channel?style=for-the-badge&color=lightgrey&label=Licença" alt="License">
</p>

O **EPG-TCL-Channel** é um gerador automatizado de playlists IPTV (`.m3u8`) e guias de programação (`.xml` no padrão XMLTV) focado na infraestrutura oficial de canais FAST da **TCL TV Plus / Ideonow**. 

O projeto roda de forma 100% autônoma através do GitHub Actions, realizando chamadas otimizadas à API de metadados, assinando digitalmente os tokens das streams e gerando a grade de horários perfeitamente sincronizada.

---

## 🌎 Status de Suporte por Região

Atualmente, o motor de raspagem está segmentando as regiões de forma gradual para garantir a estabilidade dos tokens de transmissão:

| Região | Status | Endpoint Base | Notas |
| :--- | :--- | :--- | :--- |
| **🇺🇸 United States (US)** | <kbd>🟢 OPERACIONAL</kbd> | `gateway-prod.ideonow.com` | Grade completa de canais FAST ativa com EPG detalhado por lotes. |
| **🇧🇷 Brazil (BR)** | <kbd>🟡 EM DESENVOLVIMENTO</kbd> | -- | **Próxima implementação.** Mapeando o gateway regional e CDN geobloqueada. |

---

## ⚡ Links Rápidos (Como usar no seu Player)

Copie os links abaixo e insira-os diretamente no seu aplicativo de IPTV de preferência (TiviMate, IPTV Smarters, Perfect Player, OTT Navigator, etc.).

### 📂 Playlist M3U8 (Canais)
```text
https://raw.githubusercontent.com/JulioCesarXY/EPG-TCL-Channel/main/tcl.m3u8

