
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '../services/api'

function Dashboard() {
  const navigate = useNavigate()
  const [student, setStudent] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const fetchStudent = async () => {
      try {
        const response = await api.get('/auth/me/')
        setStudent(response.data)
      } catch {
        setError('Could not load student information.')
      } finally {
        setLoading(false)
      }
    }

    fetchStudent()
  }, [])

  const handleLogout = () => {
    localStorage.removeItem('access')
    localStorage.removeItem('refresh')
    localStorage.removeItem('student_id')
    navigate('/')
  }

  const sections = [
    { title: 'Events', description: 'Explore university events and activities.', icon: '📅', path: '/events' },
    { title: 'Class Routine', description: 'View your weekly class schedule.', icon: '📚', path: '/routine' },
    { title: 'Internship', description: 'Explore internship opportunities.', icon: '💼', path: '/internships' },
    { title: 'Chatbot', description: 'Get help with your university questions.', icon: '💬', path: '/chatbot' },
  ]

  return (
    <div className="min-h-screen bg-slate-100">
      <nav className="flex flex-wrap items-center justify-between gap-4 bg-white px-6 py-5 shadow-sm md:px-10">
        <h1 className="text-2xl font-bold text-blue-700">CampusWise</h1>

        <div className="flex items-center gap-3">
          {student?.role === 'admin' && (
            <Link
              to="/admin/internships"
              className="rounded-lg bg-indigo-700 px-4 py-2 font-semibold text-white shadow hover:bg-indigo-800 text-sm"
            >
              ⚙️ Admin Internships
            </Link>
          )}

          <Link
            to="/profile"
            className="rounded-lg border border-blue-600 px-4 py-2 font-medium text-blue-600 hover:bg-blue-50"
          >
            Edit Profile
          </Link>

          <button
            onClick={handleLogout}
            className="rounded-lg bg-red-600 px-4 py-2 text-white hover:bg-red-700"
          >
            Logout
          </button>
        </div>
      </nav>

      <main className="mx-auto max-w-6xl px-6 py-12">
        <div className="mb-10">
          {loading ? (
            <p className="text-gray-600">Loading student information...</p>
          ) : error ? (
            <p className="text-red-600">{error}</p>
          ) : student ? (
            <div className="flex items-center gap-5">
              {student.profile_image ? (
                <img
                  src={student.profile_image}
                  alt="Profile"
                  className="h-20 w-20 rounded-full border-2 border-blue-200 object-cover"
                />
              ) : (
                <div className="flex h-20 w-20 items-center justify-center rounded-full bg-blue-100 text-3xl font-bold text-blue-700">
                  {student.first_name?.charAt(0) || student.student_id?.charAt(0) || 'S'}
                </div>
              )}

              <div>
                <h2 className="text-2xl font-bold text-gray-800">
                  Welcome, {`${student.first_name || ''} ${student.last_name || ''}`.trim() || student.student_id}!
                </h2>

                <p className="mt-1 text-gray-600">
                  Student ID: {student.student_id}
                </p>

                <p className="text-gray-500">
                  {student.department} {student.batch && `• Batch ${student.batch}`} {student.section && `• Section ${student.section}`}
                </p>
              </div>
            </div>
          ) : null}
        </div>

        <h3 className="mb-6 text-xl font-semibold text-gray-800">
          Explore CampusWise
        </h3>

        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
          {sections.map((section) => (
            <Link
              key={section.path}
              to={section.path}
              className="rounded-xl bg-white p-8 shadow-sm transition hover:-translate-y-1 hover:shadow-lg"
            >
              <div className="mb-5 text-4xl">{section.icon}</div>
              <h4 className="text-xl font-bold text-gray-800">{section.title}</h4>
              <p className="mt-2 text-gray-500">{section.description}</p>
              <p className="mt-5 font-semibold text-blue-600">Open Section →</p>
            </Link>
          ))}
        </div>
      </main>
    </div>
  )
}

export default Dashboard