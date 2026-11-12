
import { Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Profile from './pages/Profile'
import Internships from './pages/Internships'
import InternshipDetail from './pages/InternshipDetail'
import AdminInternships from './pages/AdminInternships'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/profile" element={<Profile />} />
      <Route path="/internships" element={<Internships />} />
      <Route path="/internships/:id" element={<InternshipDetail />} />
      <Route path="/admin/internships" element={<AdminInternships />} />
      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  )
}

export default App
