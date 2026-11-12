import { useEffect, useState, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '../services/api'

function Internships() {
  const navigate = useNavigate()

  const [internships, setInternships] = useState([])
  const [bookmarks, setBookmarks] = useState([])
  const [userRole, setUserRole] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Filter & Search states
  const [activeTab, setActiveTab] = useState('all') // 'all' or 'saved'
  const [search, setSearch] = useState('')
  const [employmentType, setEmploymentType] = useState('')
  const [statusFilter, setStatusFilter] = useState('open')
  const [sortBy, setSortBy] = useState('newest')

  // Fetch user profile to detect role
  useEffect(() => {
    const fetchUser = async () => {
      try {
        const res = await api.get('/auth/me/')
        if (res.data?.role) {
          setUserRole(res.data.role)
        }
      } catch (err) {
        // If unauthenticated, redirect to login
        if (err.response?.status === 401) {
          navigate('/')
        }
      }
    }
    fetchUser()
  }, [navigate])

  // Fetch internships
  const fetchInternships = async () => {
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams()
      if (search) params.append('search', search)
      if (employmentType) params.append('employment_type', employmentType)
      if (statusFilter) params.append('status', statusFilter)
      if (sortBy) params.append('sort', sortBy)

      const [internResp, bookmarkResp] = await Promise.all([
        api.get(`/internships/?${params.toString()}`),
        api.get('/internships/bookmarks/'),
      ])

      setInternships(internResp.data || [])
      setBookmarks(bookmarkResp.data || [])
    } catch (err) {
      if (err.response?.status === 401) {
        navigate('/')
      } else {
        setError('Could not load internship opportunities. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchInternships()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, employmentType, statusFilter, sortBy])

  // Toggle bookmark handler
  const handleToggleBookmark = async (e, id, isCurrentlyBookmarked) => {
    e.preventDefault()
    e.stopPropagation()

    try {
      if (isCurrentlyBookmarked) {
        await api.delete(`/internships/${id}/bookmark/`)
      } else {
        await api.post(`/internships/${id}/bookmark/`)
      }

      // Update local state immediately
      setInternships((prev) =>
        prev.map((item) =>
          item.id === id ? { ...item, is_bookmarked: !isCurrentlyBookmarked } : item
        )
      )

      // Refresh bookmarks list
      const bookmarkResp = await api.get('/internships/bookmarks/')
      setBookmarks(bookmarkResp.data || [])
    } catch {
      alert('Could not update bookmark. Please try again.')
    }
  }

  // Display list depending on activeTab
  const displayedInternships = useMemo(() => {
    if (activeTab === 'saved') {
      return bookmarks
    }
    return internships
  }, [activeTab, internships, bookmarks])

  return (
    <div className="min-h-screen bg-slate-100 pb-16">
      {/* Top Navbar */}
      <nav className="flex flex-wrap items-center justify-between gap-4 bg-white px-6 py-4 shadow-sm md:px-10">
        <div className="flex items-center gap-3">
          <Link to="/dashboard" className="text-2xl font-bold text-blue-700 hover:opacity-90">
            CampusWise
          </Link>
          <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
            Internship Portal
          </span>
        </div>

        <div className="flex items-center gap-3">
          {userRole === 'admin' && (
            <Link
              to="/admin/internships"
              className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-800"
            >
              ⚙️ Admin Management
            </Link>
          )}

          <Link
            to="/dashboard"
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            ← Dashboard
          </Link>
        </div>
      </nav>

      {/* Main Container */}
      <main className="mx-auto max-w-6xl px-4 py-8 md:px-8">
        {/* Header Hero */}
        <div className="mb-8 rounded-2xl bg-gradient-to-r from-blue-700 to-indigo-800 p-8 text-white shadow-md">
          <div className="max-w-2xl">
            <h1 className="text-3xl font-extrabold tracking-tight md:text-4xl">
              Career & Internship Notices
            </h1>
            <p className="mt-2 text-blue-100">
              Verified internship placements and career opportunities curated directly from the Career Development Center (CDC).
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="mb-6 flex border-b border-gray-200">
          <button
            onClick={() => setActiveTab('all')}
            className={`border-b-2 px-6 py-3 text-sm font-semibold transition ${
              activeTab === 'all'
                ? 'border-blue-700 text-blue-700'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            All Notices ({internships.length})
          </button>
          <button
            onClick={() => setActiveTab('saved')}
            className={`border-b-2 px-6 py-3 text-sm font-semibold transition ${
              activeTab === 'saved'
                ? 'border-blue-700 text-blue-700'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Bookmarked Internships ({bookmarks.length})
          </button>
        </div>

        {/* Filter & Search Bar */}
        <div className="mb-8 rounded-xl bg-white p-5 shadow-sm">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            {/* Search Input */}
            <div className="md:col-span-2">
              <label className="mb-1 block text-xs font-semibold text-gray-500 uppercase">
                Search Keywords
              </label>
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by company, title, or skills..."
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm outline-none focus:border-blue-600 focus:ring-1 focus:ring-blue-600"
              />
            </div>

            {/* Employment Type */}
            <div>
              <label className="mb-1 block text-xs font-semibold text-gray-500 uppercase">
                Workplace Type
              </label>
              <select
                value={employmentType}
                onChange={(e) => setEmploymentType(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-blue-600"
              >
                <option value="">All Types</option>
                <option value="On-site">On-site</option>
                <option value="Remote">Remote</option>
                <option value="Hybrid">Hybrid</option>
                <option value="Full-time">Full-time</option>
                <option value="Part-time">Part-time</option>
              </select>
            </div>

            {/* Sort Order */}
            <div>
              <label className="mb-1 block text-xs font-semibold text-gray-500 uppercase">
                Sort By
              </label>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-blue-600"
              >
                <option value="newest">Newest First</option>
                <option value="deadline">Nearest Deadline</option>
              </select>
            </div>
          </div>

          {activeTab === 'all' && (
            <div className="mt-4 flex items-center gap-3 border-t border-gray-100 pt-3">
              <span className="text-xs font-semibold text-gray-500">Status:</span>
              <button
                type="button"
                onClick={() => setStatusFilter('open')}
                className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                  statusFilter === 'open'
                    ? 'bg-green-100 text-green-800 font-bold'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Open Only
              </button>
              <button
                type="button"
                onClick={() => setStatusFilter('all')}
                className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                  statusFilter === 'all'
                    ? 'bg-blue-100 text-blue-800 font-bold'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                All (Including Closed)
              </button>
            </div>
          )}
        </div>

        {/* Content Area */}
        {error && (
          <div className="mb-6 rounded-lg bg-red-50 p-4 text-sm text-red-700">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex h-64 items-center justify-center">
            <p className="text-gray-500">Loading internship notices...</p>
          </div>
        ) : displayedInternships.length === 0 ? (
          <div className="rounded-2xl bg-white p-12 text-center shadow-sm">
            <span className="text-5xl">💼</span>
            <h3 className="mt-4 text-lg font-bold text-gray-800">No Internships Found</h3>
            <p className="mt-1 text-sm text-gray-500">
              {activeTab === 'saved'
                ? "You haven't bookmarked any internships yet. Click the bookmark icon on any notice to save it."
                : 'No internship notices match your current filters. Try searching for different keywords.'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            {displayedInternships.map((intern) => (
              <div
                key={intern.id}
                className="flex flex-col justify-between rounded-xl bg-white p-6 shadow-sm transition hover:shadow-md"
              >
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-100 text-xl font-bold text-blue-700">
                        {intern.company_name?.charAt(0) || '🏢'}
                      </div>
                      <div>
                        <h2 className="text-lg font-bold text-gray-800 line-clamp-1">
                          {intern.position}
                        </h2>
                        <p className="text-sm font-medium text-gray-600">{intern.company_name}</p>
                      </div>
                    </div>

                    {/* Bookmark Action */}
                    <button
                      onClick={(e) => handleToggleBookmark(e, intern.id, intern.is_bookmarked)}
                      className="rounded-full p-2 text-gray-400 hover:bg-gray-100 hover:text-blue-600 transition"
                      title={intern.is_bookmarked ? 'Remove Bookmark' : 'Save Internship'}
                    >
                      {intern.is_bookmarked ? (
                        <span className="text-xl text-yellow-500">★</span>
                      ) : (
                        <span className="text-xl text-gray-300 hover:text-gray-500">☆</span>
                      )}
                    </button>
                  </div>

                  {/* Metadata Tags */}
                  <div className="mt-4 flex flex-wrap items-center gap-2">
                    {intern.employment_type && (
                      <span className="rounded-md bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700">
                        {intern.employment_type}
                      </span>
                    )}
                    {intern.location && (
                      <span className="rounded-md bg-gray-100 px-2.5 py-1 text-xs text-gray-700">
                        📍 {intern.location}
                      </span>
                    )}
                    {intern.stipend && (
                      <span className="rounded-md bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">
                        💰 {intern.stipend}
                      </span>
                    )}
                  </div>

                  {/* Short Description */}
                  <p className="mt-4 text-sm text-gray-600 line-clamp-2">
                    {intern.description}
                  </p>

                  {/* Skills preview */}
                  {intern.required_skills && intern.required_skills.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1">
                      {intern.required_skills.slice(0, 4).map((skill, idx) => (
                        <span
                          key={idx}
                          className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-700"
                        >
                          {skill}
                        </span>
                      ))}
                      {intern.required_skills.length > 4 && (
                        <span className="text-xs text-gray-400">
                          +{intern.required_skills.length - 4} more
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {/* Footer with Deadline & CTA */}
                <div className="mt-6 border-t border-gray-100 pt-4 flex items-center justify-between">
                  <div>
                    {intern.status === 'closed' || intern.is_expired ? (
                      <span className="rounded-full bg-red-100 px-2.5 py-1 text-xs font-bold text-red-700">
                        Closed
                      </span>
                    ) : intern.days_left !== null && intern.days_left <= 3 ? (
                      <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-bold text-amber-800">
                        ⏳ Ends in {intern.days_left === 0 ? 'Today' : `${intern.days_left}d`}
                      </span>
                    ) : intern.application_deadline ? (
                      <span className="text-xs text-gray-500">
                        Deadline: {intern.application_deadline}
                      </span>
                    ) : (
                      <span className="text-xs text-gray-400">Open Deadline</span>
                    )}
                  </div>

                  <Link
                    to={`/internships/${intern.id}`}
                    className="rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-blue-700"
                  >
                    View Details →
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}

export default Internships
