import { Navigate, Route, Routes } from 'react-router'
import { AppLayout } from './components/layout'
import { NovaTriagemPage } from './pages/NovaTriagemPage'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { ProcessamentoPage } from './pages/ProcessamentoPage'
import { ResultadoPage } from './pages/ResultadoPage'

function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Navigate to="/nova-triagem" replace />} />
        <Route path="nova-triagem" element={<NovaTriagemPage />} />
        <Route path="nova-triagem/processamento/:documentoId" element={<ProcessamentoPage />} />
        <Route path="resultado/:documentoId" element={<ResultadoPage />} />
        <Route path="triagens" element={<PlaceholderPage title="Triagens e filas" />} />
        <Route path="meus-documentos" element={<PlaceholderPage title="Meus documentos" />} />
        <Route path="*" element={<Navigate to="/nova-triagem" replace />} />
      </Route>
    </Routes>
  )
}

export default App
