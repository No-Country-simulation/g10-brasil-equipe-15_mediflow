import { Navigate, Route, Routes } from 'react-router'
import { AppLayout } from './components/layout'
import { NovaTriagemPage } from './pages/NovaTriagemPage'
import { PlaceholderPage } from './pages/PlaceholderPage'

function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Navigate to="/nova-triagem" replace />} />
        <Route path="nova-triagem" element={<NovaTriagemPage />} />
        <Route path="triagens" element={<PlaceholderPage title="Triagens e filas" />} />
        <Route path="meus-documentos" element={<PlaceholderPage title="Meus documentos" />} />
        <Route path="*" element={<Navigate to="/nova-triagem" replace />} />
      </Route>
    </Routes>
  )
}

export default App
