import { useState } from 'react'
import { Badge, Button, Field, Input, SegmentedControl, Select } from './components/ui'

function App() {
  const [tipo, setTipo] = useState<'arquivo' | 'texto'>('arquivo')

  return (
    <main className="flex max-w-xl flex-col gap-6 p-8">
      <h1 className="text-heading font-semibold">MediFlow</h1>
      <SegmentedControl
        aria-label="Tipo de envio"
        value={tipo}
        onChange={setTipo}
        options={[
          { value: 'arquivo', label: 'Arquivo' },
          { value: 'texto', label: 'Texto' },
        ]}
      />
      <div className="flex gap-4">
        <Field label="Canal de origem" htmlFor="canal">
          <Select id="canal" defaultValue="ps">
            <option value="ps">Pronto-socorro</option>
          </Select>
        </Field>
        <Field label="ID do documento" hint="(opcional)" htmlFor="id">
          <Input id="id" placeholder="Gerado automaticamente" />
        </Field>
      </div>
      <div className="flex gap-2">
        <Badge tone="neutral">Rotina</Badge>
        <Badge tone="success">Processado</Badge>
        <Badge tone="danger">Urgente</Badge>
        <Badge tone="warning" size="L">EM_REVISAO</Badge>
        <Badge tone="info">Info</Badge>
        <Badge tone="error">ERRO</Badge>
      </div>
      <div className="flex gap-3">
        <Button withIcon>Enviar para triagem</Button>
        <Button disabled>Enviar para triagem</Button>
        <Button variant="secondary">Abrir</Button>
        <Button variant="secondary" size="S">Abrir</Button>
      </div>
    </main>
  )
}

export default App
