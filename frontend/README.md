# MediFlow — Portal Web (React)

Portal corporativo do MediFlow, construído a partir do design do Figma **MediFlow** e consumindo a API FastAPI do repositório.

**Stack:** Vite 8 · React 19 · TypeScript · Tailwind CSS 4 · React Router · Vitest

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
| `npm test` | Testes (Vitest + Testing Library) em execução única |
| `npm run test:watch` | Testes em modo observação |

## Variáveis de ambiente

Copie `.env.example` para `.env` para sobrescrever os padrões:

| Variável | Padrão | Uso |
|---|---|---|
| `VITE_API_URL` | vazio (mesma origem) | URL base da API usada pelo cliente HTTP. Em produção, aponte para o endereço do backend. |
| `VITE_PROXY_TARGET` | `http://localhost:8000` | Destino do proxy `/api` no servidor de desenvolvimento |
| `VITE_USAR_FIXTURES` | `false` | `true` liga o modo demo (veja abaixo) |

## Modo demo (sem backend)

Com `VITE_USAR_FIXTURES=true` no `.env` (ou `VITE_USAR_FIXTURES=true npm run dev`), o cliente da API passa a usar um simulador local (`src/services/apiSimulada.ts`). Não precisa de backend nem de chave do Gemini.

- O envio é aceito (202) e a tela de Processamento acompanha a triagem: `RECEBIDO` (2 s) → `PROCESSANDO` (10 s) → estado final.
- O cenário final depende do documento enviado. Os três casos de teste da Nova triagem cobrem os três: rotina (`PROCESSADO`, prontuário), urgente (`PROCESSADO`, fila de urgência com alerta) e ambíguo (`EM_REVISAO`, revisão humana). Qualquer outro documento cai em rotina.
- As respostas finais vêm dos JSONs de `src/fixtures/` (cenários da demo). Os dados simulados ficam no `sessionStorage`, então sobrevivem a um F5 mas não a fechar a aba.

## Estrutura

```text
src/
├── assets/icons/        SVGs da Biblioteca do Figma
├── components/
│   ├── ui/              Button, Badge, Field, Input, Select, SegmentedControl, Icon
│   ├── processamento/   etapas, barra de progresso, card Envio (Figma 02)
│   ├── resultado/       banners, cards, histórico, alerta de erro, painel JSON (Figma 03)
│   ├── triagens/        cards de fila, tabela, faixa do médico (Figma 04)
│   ├── sessao/          SessaoProvider e RotaProtegida (login de demonstração)
│   └── layout/          AppLayout, Sidebar, NavItem, UserCard, DemoNotice, PageHeader
├── lib/                 utilitários (cx)
├── pages/               telas (Nova triagem, Processamento, Resultado, Triagens e filas)
├── hooks/               useSubmeterTriagem
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
| `/login` | Login (Figma 00a–00c) | pronta, login de demonstração (veja abaixo); as demais rotas exigem sessão |
| `/nova-triagem` | Nova triagem (Figma 01a/01b) | pronta, integrada à API |
| `/nova-triagem/processamento/:id` | Processamento (Figma 02a/02b) | pronta, acompanha `/status` a cada 2 s |
| `/resultado/:id` | Resultado (Figma 03a–03e) | pronta, lê `GET /triagens/{id}` e `/historico`; reprocessa a persistência em `ERRO_PERSISTENCIA` |
| `/triagens` | Triagens e filas (Figma 04a/04b) | pronta, com lista provisória (veja abaixo); filtro na URL: `?fila=urgencia\|revisao\|processados\|andamento\|erro` |
| `/meus-documentos` | Meus documentos (Figma 04c) | pronta, filtra pelo CRM da médica de demonstração |

### Login de demonstração

O login é **fake**, só no front (não há autenticação no backend). Entra apenas a conta de demonstração:

| CRM | UF | Senha |
|---|---|---|
| `145892` | `SP` | `mediflow` |

A credencial fica em `src/lib/sessao.ts`. A sessão vai para o `sessionStorage` (ou `localStorage` com "Manter conectado") e expira após 30 min sem navegar. 5 tentativas erradas bloqueiam o login por 15 min, contadas no navegador. Nada disso é segurança: é só o estado de "logado" da demonstração.

**Acesso restrito (00d):** o Resultado bloqueia um documento quando o CRM do solicitante extraído não é o da sessão **e** o documento não foi enviado por este navegador (quem envia sempre vê o que enviou).

### Lista provisória de triagens

A API ainda não tem `GET /api/v1/triagens`. Até lá, a Nova triagem guarda no `localStorage` o ID, o canal e a hora de cada envio aceito (até 50), e `src/services/listarTriagens.ts` consulta `/status` (e o resultado, quando concluída) de cada ID. Por isso a lista mostra só os documentos enviados **neste navegador**. IDs que a API não conhece mais (404, por exemplo depois de reiniciar o backend, que guarda tudo em memória) saem da lista. Quando o endpoint existir, basta trocar a implementação de `listarTriagens`.
