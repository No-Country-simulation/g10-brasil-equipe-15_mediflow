import { Navigate, Route, Routes } from 'react-router'
import { AppLayout } from './components/layout'
import { PlaceholderPage } from './pages/PlaceholderPage'

function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Navigate to="/nova-triagem" replace />} />
        <Route
          path="nova-triagem"
          element={
            <PlaceholderPage
              title="Nova triagem"
              subtitle="Envie um documento clínico ou cole o texto. O MediFlow classifica, extrai os dados e decide o destino."
            />
          }
        />
        <Route path="triagens" element={<PlaceholderPage title="Triagens e filas" />} />
        <Route path="meus-documentos" element={<PlaceholderPage title="Meus documentos" />} />
        <Route path="*" element={<Navigate to="/nova-triagem" replace />} />
      </Route>
    </Routes>
  )
}

export default App
