import { Navigate, Route, Routes } from 'react-router'
import { AppLayout } from './components/layout'
import { RotaProtegida, SessaoProvider } from './components/sessao'
import { LoginPage } from './pages/LoginPage'
import { ListaTriagensPage } from './pages/ListaTriagensPage'
import { NovaTriagemPage } from './pages/NovaTriagemPage'
import { ProcessamentoPage } from './pages/ProcessamentoPage'
import { ResultadoPage } from './pages/ResultadoPage'

function App() {
  return (
    <SessaoProvider>
      <Routes>
        <Route path="login" element={<LoginPage />} />
        <Route element={<RotaProtegida />}>
          <Route element={<AppLayout />}>
            <Route index element={<Navigate to="/nova-triagem" replace />} />
            <Route path="nova-triagem" element={<NovaTriagemPage />} />
            <Route path="nova-triagem/processamento/:documentoId" element={<ProcessamentoPage />} />
            <Route path="resultado/:documentoId" element={<ResultadoPage />} />
            <Route path="triagens" element={<ListaTriagensPage variante="triagens" />} />
            <Route path="meus-documentos" element={<ListaTriagensPage variante="meus" />} />
            <Route path="*" element={<Navigate to="/nova-triagem" replace />} />
          </Route>
        </Route>
      </Routes>
    </SessaoProvider>
  )
}

export default App
