
import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import api from '../services/api'

function Profile() {
  const navigate = useNavigate()

  const [profile, setProfile] = useState({
    first_name: '',
    last_name: '',
    student_id: '',
    email: '',
    department: '',
    batch: '',
    section: '',
    profile_image: null,
  })

  const [image, setImage] = useState(null)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const [passwords, setPasswords] = useState({
    old_password: '',
    new_password: '',
    confirm_password: '',
  })

  const [passwordMessage, setPasswordMessage] = useState('')
  const [passwordError, setPasswordError] = useState('')

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const response = await api.get('/auth/me/')
        setProfile(response.data)
      } catch (err) {
        if (err.response?.status === 401) {
          navigate('/')
        } else {
          setError('Could not load profile.')
        }
      } finally {
        setLoading(false)
      }
    }

    fetchProfile()
  }, [navigate])

  const handleChange = (e) => {
    setProfile({
      ...profile,
      [e.target.name]: e.target.value,
    })
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setMessage('')
    setError('')

    try {
      const formData = new FormData()

      formData.append('first_name', profile.first_name)
      formData.append('last_name', profile.last_name)
      formData.append('department', profile.department)
      formData.append('batch', profile.batch)
      formData.append('section', profile.section)

      if (image) {
        formData.append('profile_image', image)
      }

      const response = await api.patch('/auth/me/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })

      setProfile(response.data)
      setImage(null)
      setMessage('Profile updated successfully!')
    } catch (err) {
      setError('Could not update profile. Please try again.')
    }
  }

  const handlePasswordChange = async (e) => {
    e.preventDefault()
    setPasswordMessage('')
    setPasswordError('')

    if (passwords.new_password !== passwords.confirm_password) {
      setPasswordError('New passwords do not match.')
      return
    }

    try {
      const response = await api.post('/auth/change-password/', {
        old_password: passwords.old_password,
        new_password: passwords.new_password,
      })

      setPasswordMessage(response.data.message)
      setPasswords({
        old_password: '',
        new_password: '',
        confirm_password: '',
      })
    } catch (err) {
      const errorData = err.response?.data
      setPasswordError(
        errorData?.error?.toString() || 'Could not change password.'
      )
    }
  }

  if (loading) {
    return <p className="p-10 text-center">Loading profile...</p>
  }

  return (
    <div className="min-h-screen bg-slate-100 px-6 py-10">
      <div className="mx-auto max-w-2xl rounded-xl bg-white p-8 shadow-md">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-bold text-blue-700">Edit Profile</h1>
          <Link to="/dashboard" className="text-blue-600 hover:underline">
            Back to Dashboard
          </Link>
        </div>

        {error && <p className="mb-4 text-red-600">{error}</p>}
        {message && <p className="mb-4 text-green-600">{message}</p>}

        <form onSubmit={handleSave} className="space-y-5">
          <div>
            <label className="mb-2 block font-medium">Profile Picture</label>

            {image ? (
              <img
                src={URL.createObjectURL(image)}
                alt="Selected profile"
                className="mb-3 h-24 w-24 rounded-full object-cover"
              />
            ) : profile.profile_image ? (
              <img
                src={profile.profile_image}
                alt="Profile"
                className="mb-3 h-24 w-24 rounded-full object-cover"
              />
            ) : null}

            <input
              type="file"
              accept="image/*"
              onChange={(e) => setImage(e.target.files[0] || null)}
              className="w-full"
            />
          </div>

          <div>
            <label className="mb-2 block font-medium">First Name</label>
            <input
              name="first_name"
              value={profile.first_name}
              onChange={handleChange}
              className="w-full rounded-lg border p-3"
            />
          </div>

          <div>
            <label className="mb-2 block font-medium">Last Name</label>
            <input
              name="last_name"
              value={profile.last_name}
              onChange={handleChange}
              className="w-full rounded-lg border p-3"
            />
          </div>

          <div>
            <label className="mb-2 block font-medium">Student ID</label>
            <input
              value={profile.student_id}
              disabled
              className="w-full rounded-lg border bg-gray-100 p-3"
            />
          </div>

          <div>
            <label className="mb-2 block font-medium">Email</label>
            <input
              value={profile.email}
              disabled
              className="w-full rounded-lg border bg-gray-100 p-3"
            />
          </div>

          <div>
            <label className="mb-2 block font-medium">Department</label>
            <input
              name="department"
              value={profile.department}
              onChange={handleChange}
              className="w-full rounded-lg border p-3"
            />
          </div>

          <div>
            <label className="mb-2 block font-medium">Batch</label>
            <input
              name="batch"
              value={profile.batch}
              onChange={handleChange}
              className="w-full rounded-lg border p-3"
            />
          </div>

          <div>
            <label className="mb-2 block font-medium">Section</label>
            <input
              name="section"
              value={profile.section}
              onChange={handleChange}
              className="w-full rounded-lg border p-3"
            />
          </div>

          <button
            type="submit"
            className="w-full rounded-lg bg-blue-600 py-3 font-semibold text-white hover:bg-blue-700"
          >
            Save Changes
          </button>
        </form>

        <div className="mt-10 border-t pt-6">
          <h2 className="mb-5 text-xl font-bold">Change Password</h2>

          {passwordError && (
            <p className="mb-4 text-red-600">{passwordError}</p>
          )}

          {passwordMessage && (
            <p className="mb-4 text-green-600">{passwordMessage}</p>
          )}

          <form onSubmit={handlePasswordChange} className="space-y-4">
            <input
              type="password"
              placeholder="Current Password"
              value={passwords.old_password}
              onChange={(e) =>
                setPasswords({ ...passwords, old_password: e.target.value })
              }
              required
              className="w-full rounded-lg border p-3"
            />

            <input
              type="password"
              placeholder="New Password"
              value={passwords.new_password}
              onChange={(e) =>
                setPasswords({ ...passwords, new_password: e.target.value })
              }
              required
              className="w-full rounded-lg border p-3"
            />

            <input
              type="password"
              placeholder="Confirm New Password"
              value={passwords.confirm_password}
              onChange={(e) =>
                setPasswords({ ...passwords, confirm_password: e.target.value })
              }
              required
              className="w-full rounded-lg border p-3"
            />

            <button
              type="submit"
              className="w-full rounded-lg bg-green-600 py-3 font-semibold text-white hover:bg-green-700"
            >
              Change Password
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}

export default Profile