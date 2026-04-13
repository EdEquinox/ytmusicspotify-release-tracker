# Atualizacao automatica (GitHub -> GHCR -> Portainer)

Este projeto esta preparado para atualizar automaticamente no servidor sempre que fizeres push para `main`.

## 1) O que ja ficou preparado

- Workflow GitHub Actions: `.github/workflows/deploy-portainer.yml`
- Imagens no compose de Portainer com tag `latest`:
  - `ghcr.io/edequinox/ytmusic-release-tracker-frontend:latest`
  - `ghcr.io/edequinox/ytmusic-release-tracker-backend:latest`
  - `ghcr.io/edequinox/ytmusic-release-tracker-worker:latest`

## 2) Configurar permissao de packages no repo

No GitHub, no repo:

- `Settings` -> `Actions` -> `General`
- Em `Workflow permissions`, selecionar **Read and write permissions**
- Guardar.

Sem isto, o workflow nao consegue fazer push para GHCR com `GITHUB_TOKEN`.

## 3) Criar webhook no Portainer

No Portainer, abre o stack da aplicacao e ativa webhook de update.
Depois copia a URL do webhook.

## 4) Adicionar secret no GitHub

No GitHub, no repo:

- `Settings` -> `Secrets and variables` -> `Actions`
- `New repository secret`
- Nome: `PORTAINER_WEBHOOK_URL`
- Valor: URL do webhook do Portainer

## 5) Fluxo de update

1. Faz alteracoes no codigo
2. `git add . && git commit -m "..." && git push`
3. O workflow:
   - builda e publica as 3 imagens no GHCR (`latest` + `sha`)
   - chama webhook do Portainer
4. O Portainer faz redeploy do stack com as imagens mais recentes

## 6) Validacao rapida

Depois de cada push, verifica:

- Aba `Actions` no GitHub -> workflow `Build And Deploy To Portainer` com sucesso
- Logs do stack no Portainer (backend/worker/frontend)
- Frontend acessivel e funcional
