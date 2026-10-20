# 🤝 Guia de Colaboração e Fluxo Git — Equipe 15 MediFlow

Bem-vindo ao repositório do **MediFlow** (Hackathon ONE G10 — Oracle & Alura)!
Para que nossa equipe de 7 a 8 pessoas trabalhe com agilidade sem conflitos de código, adotamos o **Feature Branch Workflow**.

---

## 🌳 Arquitetura de Branches

| Branch | Função | Regra de Acesso |
|---|---|---|
| `main` | Código de produção, estável para entrega e avaliação final. | **Protegida**. Pushes diretos bloqueados. Merge somente via PR vindo de `develop`. |
| `develop` | Branch padrão (*default*). Onde todas as funcionalidades se integram. | **Protegida**. Pushes diretos bloqueados. Merge somente via Pull Request aprovado. |
| `feature/*` | Desenvolvimento de novas funcionalidades. | Criada a partir de `develop` e mesclada de volta via PR. |
| `fix/*` | Correção pontual de bugs identificados na `develop`. | Criada a partir de `develop` e mesclada de volta via PR. |
| `docs/*` | Atualizações de documentação, guias e diagramas. | Criada a partir de `develop` e mesclada de volta via PR. |

---

## 🚀 Ciclo de Trabalho no Dia a Dia (Passo a Passo)

### 1. Atualizar sua base local antes de começar
Antes de iniciar qualquer tarefa, certifique-se de que sua `develop` local está sincronizada com o GitHub:
```bash
git checkout develop
git pull origin develop
```

### 2. Criar uma nova branch para sua tarefa
Crie e entre em uma branch com um nome descritivo em minúsculas e separado por hífens:
```bash
# Para uma funcionalidade nova:
git checkout -b feature/extracao-gemini

# Para uma correção:
git checkout -b fix/parser-pdf-invalido

# Para documentação:
git checkout -b docs/diagrama-langgraph
```

### 3. Desenvolver e salvar suas alterações (Commits)
Faça alterações e salve seus commits em etapas pequenas e com mensagens claras, usando o padrão **Conventional Commits**:
```bash
git add .
git commit -m "feat: adiciona extracao de dados clinicos com gemini"
```

#### Prefixos recomendados:
- `feat:` Nova funcionalidade.
- `fix:` Correção de bug.
- `docs:` Alterações na documentação ou README.
- `refactor:` Mudança no código que não altera comportamento nem conserta bug.
- `chore:` Atualização de dependências, `.gitignore` ou configurações.

### 4. Enviar sua branch para o GitHub
Envie sua branch remota para o repositório:
```bash
git push -u origin feature/extracao-gemini
```

### 5. Abrir o Pull Request (PR) no GitHub
1. Abra o repositório no GitHub.
2. Você verá um aviso sugerindo a criação do PR da sua branch recém-enviada. Clique em **"Compare & pull request"**.
3. **ATENÇÃO:** Garanta que a branch base (destino) seja **`develop`** (ex: `base: develop` $\leftarrow$ `compare: feature/...`).
4. Preencha o formulário do Pull Request (o template será preenchido automaticamente).
5. Avise no grupo da equipe que o PR está aberto para revisão.

### 6. Revisão entre Pares (Peer Review) & Merge
- Pelo menos **1 colega da equipe** deve revisar o PR, testar se necessário e clicar em **Approve**.
- Com a aprovação, realize o **Merge** na `develop`.
- Clique no botão **Delete branch** no GitHub para manter o repositório limpo.

---

## ⚠️ Como Evitar e Resolver Conflitos (Merge Conflicts)

Se outro colega mesclou código na `develop` enquanto você ainda estava trabalhando na sua branch, atualize a sua branch antes de abrir ou finalizar o PR:

```bash
# 1. Estando na sua feature branch:
git checkout feature/sua-feature

# 2. Puxe as atualizações da develop para dentro da sua branch:
git pull origin develop

# 3. Se o Git acusar conflito, abra o VS Code/editor, resolva as marcações (Accept Incoming / Current / Both):
# 4. Após resolver, finalize o merge:
git add .
git commit -m "chore: resolve conflitos com a branch develop"
git push origin feature/sua-feature
```

---

## 🔒 Regras de Ouro
1. **Nunca suba credenciais ou chaves:** Chaves de API (Gemini, Claude, OpenAI), chaves privadas OCI (`*.pem`) e senhas devem ficar exclusivamente no arquivo `.env` local (que já está no `.gitignore`).
2. **Nunca use `git push --force`** nas branches compartilhadas (`main` ou `develop`).
3. **Mantenha PRs focados e objetivos:** PRs menores são mais fáceis e rápidos de revisar e aprovar.
