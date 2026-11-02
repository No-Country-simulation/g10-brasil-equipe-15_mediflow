# MediFlow — Portal Web (React)

Portal corporativo do MediFlow, construído a partir do design do Figma **MediFlow** e consumindo a API FastAPI do repositório.

**Stack:** Vite 8 · React 19 · TypeScript · Tailwind CSS 4 · React Router

## Pré-requisitos

- Node.js `^20.19` ou `>=22.12`
- Backend FastAPI rodando em `http://localhost:8000` (veja o [README da raiz](../README.md)):

```bash
# na raiz do repositório
uvicorn src.api.main:app --reload --port 8000
```

## Como rodar

```bash
cd frontend
npm install
npm run dev
```

O portal abre em `http://localhost:5173`. Em desenvolvimento, as chamadas para `/api/*` passam pelo proxy do Vite e são encaminhadas ao backend, então não há problema de CORS.

## Scripts

| Comando | O que faz |
|---|---|
| `npm run dev` | Servidor de desenvolvimento com HMR |
| `npm run build` | Checagem de tipos (`tsc -b`) e build de produção em `dist/` |
| `npm run preview` | Serve o build de produção localmente |
| `npm run lint` | Lint com oxlint |

## Variáveis de ambiente

Copie `.env.example` para `.env` para sobrescrever os padrões:

| Variável | Padrão | Uso |
|---|---|---|
| `VITE_API_URL` | vazio (mesma origem) | URL base da API usada pelo cliente HTTP. Em produção, aponte para o endereço do backend. |
| `VITE_PROXY_TARGET` | `http://localhost:8000` | Destino do proxy `/api` no servidor de desenvolvimento |

## Estrutura

```text
src/
├── assets/icons/        SVGs da Biblioteca do Figma
├── components/
│   ├── ui/              Button, Badge, Field, Input, Select, SegmentedControl, Icon
│   └── layout/          AppLayout, Sidebar, NavItem, UserCard, DemoNotice, PageHeader
├── lib/                 utilitários (cx)
├── pages/               telas (hoje, apenas PlaceholderPage)
├── services/api.ts      cliente HTTP da API e ApiError
├── types/               contrato clínico (clinical.ts) e DTOs da API (api.ts)
├── index.css            Tailwind e tokens do design system (@theme)
└── main.tsx
```

## Design system

Os tokens (cores, tipografia, raios, sombra) estão no bloco `@theme` de `src/index.css` e foram extraídos do Figma. Eles viram classes do Tailwind, por exemplo `bg-primary`, `text-text-secondary`, `bg-sidebar` e `rounded-md`. Fontes: IBM Plex Sans e IBM Plex Mono (pacotes `@fontsource`).

Os ícones são SVGs com `currentColor`, usados pelo componente `<Icon name="plus" size={18} />`.

> `--color-primary-hover` e os contornos de foco não existem no Figma e foram adicionados para acessibilidade.

## Contrato de dados

`src/types/clinical.ts` espelha `src/schemas/clinical.py`, a fonte única da verdade. Ao alterar o schema Python, atualize o arquivo TypeScript.

## Rotas

| Rota | Tela | Estado |
|---|---|---|
| `/nova-triagem` | Nova triagem (Figma 01a/01b) | em desenvolvimento |
| `/triagens` | Triagens e filas | placeholder (a API ainda não lista triagens) |
| `/meus-documentos` | Meus documentos | placeholder (a API ainda não tem autenticação) |

O card da médica na sidebar é fictício (a API ainda não tem login).
