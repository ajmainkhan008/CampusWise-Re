import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import api from '../services/api'

function InternshipDetail() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [internship, setInternship] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [bookmarking, setBookmarking] = useState(false)

  const fetchDetail = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await api.get(`/internships/${id}/`)
      setInternship(res.data)
    } catch (err) {
      if (err.response?.status === 401) {
        navigate('/')
      } else if (err.response?.status === 404) {
        setError('The requested internship notice was not found.')
      } else {
        setError('Could not load internship details. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchDetail()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  const handleToggleBookmark = async () => {
    if (!internship || bookmarking) return
    setBookmarking(true)

    try {
      if (internship.is_bookmarked) {
        await api.delete(`/internships/${id}/bookmark/`)
      } else {
        await api.post(`/internships/${id}/bookmark/`)
      }
      setInternship((prev) => ({
        ...prev,
        is_bookmarked: !prev.is_bookmarked,
      }))
    } catch {
      alert('Could not update bookmark.')
    } finally {
      setBookmarking(false)
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-100">
        <p className="text-gray-500">Loading internship notice details...</p>
      </div>
    )
  }

  if (error || !internship) {
    return (
      <div className="min-h-screen bg-slate-100 px-6 py-12">
        <div className="mx-auto max-w-2xl rounded-2xl bg-white p-8 text-center shadow-sm">
          <span className="text-5xl">⚠️</span>
          <h2 className="mt-4 text-xl font-bold text-gray-800">Notice Unavailable</h2>
          <p className="mt-2 text-sm text-gray-500">{error || 'Internship not found.'}</p>
          <Link
            to="/internships"
            className="mt-6 inline-block rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-blue-700"
          >
            ← Back to Internships
          </Link>
        </div>
      </div>
    )
  }

  const isClosed = internship.status === 'closed' || internship.is_expired

  return (
    <div className="min-h-screen bg-slate-100 pb-20">
      {/* Top Navbar */}
      <nav className="flex items-center justify-between bg-white px-6 py-4 shadow-sm md:px-10">
        <Link to="/internships" className="text-sm font-semibold text-blue-700 hover:underline">
          ← Back to All Internships
        </Link>
        <Link to="/dashboard" className="text-sm font-medium text-gray-600 hover:text-gray-800">
          CampusWise Dashboard
        </Link>
      </nav>

      {/* Main Container */}
      <main className="mx-auto mt-8 max-w-4xl px-4 md:px-8">
        <div className="rounded-2xl bg-white p-8 shadow-sm">
          {/* Header Banner */}
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-gray-100 pb-6">
            <div className="flex items-start gap-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-100 text-2xl font-bold text-blue-700 shadow-sm">
                {internship.company_name?.charAt(0) || '🏢'}
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900 md:text-3xl">
                  {internship.position}
                </h1>
                <p className="mt-1 text-lg font-medium text-gray-600">
                  {internship.company_name}
                </p>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <span
                    className={`rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wider ${
                      isClosed
                        ? 'bg-red-100 text-red-700'
                        : 'bg-green-100 text-green-800'
                    }`}
                  >
                    {isClosed ? 'Closed / Expired' : 'Active & Accepting Applications'}
                  </span>
                  {internship.employment_type && (
                    <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
                      {internship.employment_type}
                    </span>
                  )}
                  {internship.location && (
                    <span className="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-700">
                      📍 {internship.location}
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Bookmark button */}
            <button
              onClick={handleToggleBookmark}
              disabled={bookmarking}
              className="flex items-center gap-2 rounded-xl border border-gray-200 px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50 transition"
            >
              <span>{internship.is_bookmarked ? '★' : '☆'}</span>
              <span>{internship.is_bookmarked ? 'Saved' : 'Save Notice'}</span>
            </button>
          </div>

          {/* Quick Metrics Grid */}
          <div className="mt-6 grid grid-cols-2 gap-4 rounded-xl bg-slate-50 p-5 sm:grid-cols-4">
            <div>
              <p className="text-xs font-semibold text-gray-400 uppercase">Stipend</p>
              <p className="mt-1 text-sm font-bold text-gray-800">
                {internship.stipend || 'Unspecified / Negotiable'}
              </p>
            </div>
            <div>
              <p className="text-xs font-semibold text-gray-400 uppercase">Deadline</p>
              <p className="mt-1 text-sm font-bold text-gray-800">
                {internship.application_deadline || 'Open / Rolling'}
              </p>
            </div>
            <div>
              <p className="text-xs font-semibold text-gray-400 uppercase">Location</p>
              <p className="mt-1 text-sm font-bold text-gray-800">
                {internship.location || 'On Campus / TBD'}
              </p>
            </div>
            <div>
              <p className="text-xs font-semibold text-gray-400 uppercase">Notice Source</p>
              <p className="mt-1 text-sm font-bold text-gray-800">
                {internship.source_link ? (
                  <a
                    href={internship.source_link}
                    target="_blank"
                    rel="noreferrer"
                    className="text-blue-600 hover:underline"
                  >
                    View Official Notice ↗
                  </a>
                ) : (
                  'CDC Direct Email'
                )}
              </p>
            </div>
          </div>

          {/* Description Section */}
          <div className="mt-8">
            <h3 className="text-lg font-bold text-gray-900">About the Role</h3>
            <div className="mt-3 whitespace-pre-line text-sm leading-relaxed text-gray-700">
              {internship.description}
            </div>
          </div>

          {/* Eligibility Criteria */}
          {internship.eligibility && (
            <div className="mt-8 border-t border-gray-100 pt-6">
              <h3 className="text-lg font-bold text-gray-900">Eligibility & Requirements</h3>
              <div className="mt-3 whitespace-pre-line text-sm leading-relaxed text-gray-700">
                {internship.eligibility}
              </div>
            </div>
          )}

          {/* Required Skills */}
          {internship.required_skills && internship.required_skills.length > 0 && (
            <div className="mt-8 border-t border-gray-100 pt-6">
              <h3 className="text-lg font-bold text-gray-900">Required Skills</h3>
              <div className="mt-3 flex flex-wrap gap-2">
                {internship.required_skills.map((skill, idx) => (
                  <span
                    key={idx}
                    className="rounded-lg bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700 border border-blue-100"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Application Instructions */}
          {internship.application_instructions && (
            <div className="mt-8 border-t border-gray-100 pt-6">
              <h3 className="text-lg font-bold text-gray-900">How to Apply</h3>
              <div className="mt-3 whitespace-pre-line rounded-xl bg-blue-50/50 p-4 text-sm leading-relaxed text-blue-900 border border-blue-100">
                {internship.application_instructions}
              </div>
            </div>
          )}

          {/* Apply Action Bar */}
          <div className="mt-10 border-t border-gray-100 pt-6">
            {isClosed ? (
              <div className="rounded-xl bg-red-50 p-4 text-center">
                <p className="font-semibold text-red-700">
                  This internship deadline has passed. Applications are closed.
                </p>
              </div>
            ) : (
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <p className="text-xs text-gray-500">
                    Published: {internship.published_at ? new Date(internship.published_at).toLocaleDateString() : 'Recent'}
                  </p>
                  {internship.application_email && (
                    <p className="text-xs text-gray-600 mt-1">
                      Direct Email: <span className="font-mono font-semibold">{internship.application_email}</span>
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-3">
                  {internship.application_url && (
                    <a
                      href={internship.application_url}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-xl bg-blue-700 px-6 py-3 font-semibold text-white shadow-md hover:bg-blue-800 transition"
                    >
                      Apply on Official Portal ↗
                    </a>
                  )}

                  {!internship.application_url && internship.application_email && (
                    <a
                      href={`mailto:${internship.application_email}?subject=Application for ${encodeURIComponent(internship.position)}`}
                      className="rounded-xl bg-blue-700 px-6 py-3 font-semibold text-white shadow-md hover:bg-blue-800 transition"
                    >
                      Send Application Email ✉️
                    </a>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}

export default InternshipDetail
