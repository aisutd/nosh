import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import Presentation from './pages/Presentation.jsx'
import SampleDemo from './components/SampleDemo.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      {window.location.pathname === '/presentation' ? <Presentation /> : window.location.pathname === '/presentation-sample' ? <SampleDemo /> : <App />}
    </BrowserRouter>
  </StrictMode>,
)
