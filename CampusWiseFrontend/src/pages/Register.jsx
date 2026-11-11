
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '../services/api'

function Register() {
  const navigate = useNavigate()

  const [formData, setFormData] = useState({
    student_id: '',
    email: '',
    password: '',
    department: '',
    batch: '',
  })

  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    })
  }

  const handleRegister = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await api.post('/auth/register/', formData)

      alert('Registration successful! You can now log in.')
      navigate('/')
    } catch (err) {
      const data = err.response?.data

      if (data && typeof data === 'object') {
        const messages = Object.entries(data)
          .map(([field, value]) => {
            const message = Array.isArray(value) ? value.join(', ') : String(value)
            return `${field}: ${message}`
          })
          .join('\n')

        setError(messages || 'Registration failed. Please try again.')
      } else {
        setError('Cannot connect to the server. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100 px-4 py-10">
      <div className="w-full max-w-lg rounded-2xl bg-white p-8 shadow-xl">

        <div className="mb-7 text-center">
          <h1 className="text-3xl font-bold text-blue-700">
            CampusWise
          </h1>
          <p className="mt-2 text-gray-500">
            Create your student account.
          </p>
        </div>

        <h2 className="mb-6 text-2xl font-bold text-gray-800">
          Student Registration
        </h2>

        <form onSubmit={handleRegister} className="space-y-4">

          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              Student ID
            </label>
            <input
              name="student_id"
              value={formData.student_id}
              onChange={handleChange}
              placeholder="Example: 241-35-249"
              required
              className="w-full rounded-lg border border-gray-300 px-4 py-3 outline-none focus:border-blue-600"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              Email Address
            </label>
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              placeholder="Enter your email"
              required
              className="w-full rounded-lg border border-gray-300 px-4 py-3 outline-none focus:border-blue-600"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              Password
            </label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              placeholder="Create a password"
              required
              className="w-full rounded-lg border border-gray-300 px-4 py-3 outline-none focus:border-blue-600"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              Department
            </label>
            <input
              name="department"
              value={formData.department}
              onChange={handleChange}
              placeholder="Example: Software Engineering"
              required
              className="w-full rounded-lg border border-gray-300 px-4 py-3 outline-none focus:border-blue-600"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              Batch
            </label>
            <input
              name="batch"
              value={formData.batch}
              onChange={handleChange}
              placeholder="Example: 42"
              required
              className="w-full rounded-lg border border-gray-300 px-4 py-3 outline-none focus:border-blue-600"
            />
          </div>

          {error && (
            <pre className="whitespace-pre-wrap rounded-lg bg-red-50 p-3 text-sm text-red-600">
              {error}
            </pre>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-blue-700 py-3 font-semibold text-white transition hover:bg-blue-800 disabled:opacity-60"
          >
            {loading ? 'Creating account...' : 'Create Account'}
          </button>

        </form>

        <p className="mt-6 text-center text-sm text-gray-600">
          Already have an account?{' '}
          <Link to="/" className="font-semibold text-blue-700 hover:underline">
            Login
          </Link>
        </p>

      </div>
    </div>
  )
}

export default Register
