import { Icon } from './components/ui/Icon'

function App() {
  return (
    <main className="p-8">
      <h1 className="text-heading font-semibold">MediFlow</h1>
      <p className="mt-2 text-body text-text-secondary">Base do portal em construção.</p>
      <button
        type="button"
        className="mt-6 inline-flex items-center gap-2.5 rounded-md bg-primary px-5.5 py-3.5 font-semibold text-on-primary"
      >
        <Icon name="plus" size={18} />
        Token primário
      </button>
    </main>
  )
}

export default App
