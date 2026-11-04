import { useId, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router'
import { Button, Field, Icon, Input, Select } from '../components/ui'
import type { IconName } from '../components/ui'
import { useSessao } from '../hooks/useSessao'
import type { EstadoLogin } from '../hooks/useSessao'
import { cx } from '../lib/cx'
import { CONTA_DEMO } from '../lib/sessao'

const UFS = ['AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO']

const PONTOS = [
  'Cada médico vê apenas os documentos vinculados ao seu CRM',
  'Urgências e casos ambíguos sempre chegam à fila certa',
  'Dados fictícios · ambiente de demonstração',
]

type Aviso = { tom: 'erro' | 'info'; texto: string }

function CaixaAviso({ aviso }: { aviso: Aviso }) {
  const icone: IconName = aviso.tom === 'erro' ? 'alert' : 'info'
  return (
    <div
      role={aviso.tom === 'erro' ? 'alert' : 'status'}
      className={cx(
        'flex items-start gap-2.5 rounded-md px-3.5 py-3 text-sm leading-normal',
        aviso.tom === 'erro'
          ? 'bg-status-danger-bg text-status-danger-fg'
          : 'border border-border-info bg-selected text-info-panel-text',
      )}
    >
      <Icon name={icone} size={20} className="shrink-0" />
      <span className="flex-1">{aviso.texto}</span>
    </div>
  )
}

function PainelMarca() {
  return (
    <aside className="flex w-140 shrink-0 flex-col justify-between bg-sidebar p-14">
      <div className="flex items-center gap-2.5">
        <Icon name="logo-marca" size={32} />
        <span className="text-xl font-semibold tracking-[-0.2px] text-sidebar-text-strong">MediFlow</span>
      </div>
      <div className="flex flex-col gap-5">
        <p className="m-0 text-heading font-semibold text-sidebar-text-strong">
          Triagem clínica com IA, cada documento no lugar certo.
        </p>
        <p className="m-0 text-body text-sidebar-text">
          Agente autônomo para triagem, extração e roteamento de documentos clínicos.
        </p>
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {PONTOS.map((p) => (
            <li key={p} className="flex items-start gap-2.5 text-sm leading-normal text-sidebar-text">
              <Icon name="check" size={18} className="mt-0.5 shrink-0" />
              {p}
            </li>
          ))}
        </ul>
      </div>
      <p className="m-0 text-caption text-sidebar-text">Hackathon ONE G10 · Equipe 15</p>
    </aside>
  )
}

function horario(ms: number): string {
  return new Date(ms).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', hour12: false })
}

/** Telas 00a (padrão), 00b (credenciais inválidas) e 00c (sessão expirada). */
export function LoginPage() {
  const { sessao, entrar } = useSessao()
  const navigate = useNavigate()
  const estado = (useLocation().state ?? {}) as EstadoLogin
  const ids = { crm: useId(), uf: useId(), senha: useId(), manter: useId() }

  const [crm, setCrm] = useState('')
  const [uf, setUf] = useState('')
  const [senha, setSenha] = useState('')
  const [manter, setManter] = useState(false)
  const [verSenha, setVerSenha] = useState(false)
  const [aviso, setAviso] = useState<Aviso | null>(
    estado.motivo === 'expirada' ? { tom: 'info', texto: 'Sua sessão expirou por inatividade. Entre novamente para continuar.' } : null,
  )
  const [errou, setErrou] = useState(false)

  if (sessao) return <Navigate to={estado.de && estado.de !== '/login' ? estado.de : '/nova-triagem'} replace />

  function aoEntrar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const resultado = entrar({ crm, uf, senha }, manter)
    if (resultado.ok) {
      navigate(estado.de && estado.de !== '/login' ? estado.de : '/nova-triagem', { replace: true })
      return
    }
    setErrou(true)
    setAviso({
      tom: 'erro',
      texto:
        resultado.erro === 'bloqueado'
          ? `Acesso bloqueado por excesso de tentativas. Tente de novo às ${horario(resultado.ate)}.`
          : 'CRM, UF ou senha incorretos. Confira os dados e tente novamente.',
    })
  }

  const bordaErro = errou ? 'border-2 border-status-danger-fg' : undefined

  return (
    <div className="flex min-h-screen bg-app">
      <PainelMarca />
      <main className="flex flex-1 items-center justify-center p-12">
        <form
          noValidate
          onSubmit={aoEntrar}
          aria-labelledby="titulo-login"
          className="flex w-110 flex-col gap-6 rounded-lg border border-border bg-surface p-9"
        >
          <div className="flex flex-col gap-1.5">
            <h1 id="titulo-login" className="text-heading font-semibold text-text">
              Entrar
            </h1>
            <p className="m-0 text-sm leading-normal text-text-secondary">
              Acesse com seu CRM e senha para ver os seus documentos.
            </p>
          </div>

          {aviso && <CaixaAviso aviso={aviso} />}

          <div className="flex flex-col gap-4">
            <div className="flex gap-3">
              <Field label="CRM" htmlFor={ids.crm}>
                <Input
                  id={ids.crm}
                  inputMode="numeric"
                  autoComplete="username"
                  placeholder="Somente números"
                  value={crm}
                  onChange={(e) => setCrm(e.target.value)}
                  aria-invalid={errou || undefined}
                  className={cx('text-[15px]', bordaErro)}
                />
              </Field>
              <div className="w-27.5 shrink-0">
                <Field label="UF" htmlFor={ids.uf}>
                  <Select
                    id={ids.uf}
                    value={uf}
                    onChange={(e) => setUf(e.target.value)}
                    aria-invalid={errou || undefined}
                    className={cx(!uf && 'text-text-placeholder', bordaErro)}
                  >
                    <option value="" disabled>
                      UF
                    </option>
                    {UFS.map((u) => (
                      <option key={u} value={u}>
                        {u}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>
            </div>

            <Field label="Senha" htmlFor={ids.senha}>
              <div className="relative">
                <Input
                  id={ids.senha}
                  mono={false}
                  type={verSenha ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="Digite sua senha"
                  value={senha}
                  onChange={(e) => setSenha(e.target.value)}
                  aria-invalid={errou || undefined}
                  className={cx('pr-10 text-base', bordaErro)}
                />
                <button
                  type="button"
                  aria-label={verSenha ? 'Ocultar senha' : 'Mostrar senha'}
                  aria-pressed={verSenha}
                  onClick={() => setVerSenha((v) => !v)}
                  className="absolute top-1/2 right-3 -translate-y-1/2 cursor-pointer text-text-secondary hover:text-text focus-visible:outline-2 focus-visible:outline-primary"
                >
                  <Icon name="eye" size={18} />
                </button>
              </div>
            </Field>

            <div className="flex items-center justify-between gap-3">
              <label htmlFor={ids.manter} className="flex cursor-pointer items-center gap-2 text-sm leading-normal text-text-body">
                <input
                  id={ids.manter}
                  type="checkbox"
                  checked={manter}
                  onChange={(e) => setManter(e.target.checked)}
                  className="size-4.5 cursor-pointer accent-primary"
                />
                Manter conectado
              </label>
              <button
                type="button"
                onClick={() => setAviso({ tom: 'info', texto: 'Ambiente de demonstração: use a conta indicada abaixo.' })}
                className="cursor-pointer text-sm font-medium text-link hover:underline focus-visible:outline-2 focus-visible:outline-primary"
              >
                Esqueci minha senha
              </button>
            </div>
          </div>

          <div className="flex flex-col gap-3">
            <Button type="submit" withIcon className="w-full">
              Entrar
            </Button>
            {errou && (
              <p className="m-0 text-caption text-text-secondary">
                Após 5 tentativas incorretas o acesso fica bloqueado por 15 minutos.
              </p>
            )}
          </div>

          <ContaDemo>
            CRM {CONTA_DEMO.crm} / {CONTA_DEMO.uf} · {CONTA_DEMO.medico.nome}. Cada CRM enxerga apenas os documentos em
            que consta como solicitante.
            <br />
            Senha: <span className="font-mono">{CONTA_DEMO.senha}</span>
          </ContaDemo>
        </form>
      </main>
    </div>
  )
}

function ContaDemo({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 rounded-md border border-border-subtle bg-subtle px-3.5 py-3">
      <p className="m-0 text-caption font-medium text-text">Conta de demonstração</p>
      <p className="m-0 text-caption text-text-secondary">{children}</p>
    </div>
  )
}
