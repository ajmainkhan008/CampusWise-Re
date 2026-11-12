import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '../services/api'

function AdminInternships() {
  const navigate = useNavigate()

  // High-level states
  const [stats, setStats] = useState({
    total_internships: 0,
    published_internships: 0,
    pending_review: 0,
    closed_internships: 0,
    rejected_imports: 0,
  })
  const [activeTab, setActiveTab] = useState('overview') // 'overview' | 'import' | 'pending' | 'published' | 'closed' | 'history'
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')

  // Data lists
  const [drafts, setDrafts] = useState([])
  const [publishedList, setPublishedList] = useState([])
  const [closedList, setClosedList] = useState([])
  const [historyList, setHistoryList] = useState([])

  // Email Import Form State (FR-37, FR-58)
  const [importForm, setImportForm] = useState({
    email_subject: '',
    sender_email: 'cdc@diu.edu.bd',
    original_email_content: '',
    source_link: '',
  })
  const [importing, setImporting] = useState(false)
  const [duplicateWarning, setDuplicateWarning] = useState(null)

  // Review & Edit Modal State (FR-39)
  const [selectedDraft, setSelectedDraft] = useState(null)
  const [reviewFields, setReviewFields] = useState({
    company_name: '',
    position: '',
    description: '',
    eligibility: '',
    required_skills: '',
    location: '',
    employment_type: 'On-site',
    stipend: '',
    application_deadline: '',
    application_url: '',
    application_email: '',
    application_instructions: '',
  })
  const [rejecting, setRejecting] = useState(false)
  const [rejectReason, setRejectReason] = useState('')

  // Verify Admin Permissions (Section 11)
  useEffect(() => {
    const checkRole = async () => {
      try {
        const res = await api.get('/auth/me/')
        if (res.data?.role !== 'admin') {
          alert('Access denied: Admin role required to access Internship Management.')
          navigate('/dashboard')
        }
      } catch {
        navigate('/')
      }
    }
    checkRole()
  }, [navigate])

  // Load stats and active tab data
  const loadStats = async () => {
    try {
      const res = await api.get('/internships/admin/stats/')
      setStats(res.data)
    } catch (err) {
      console.error('Failed to load stats:', err)
    }
  }

  const loadTabData = async () => {
    setLoading(true)
    setError('')
    try {
      await loadStats()

      if (activeTab === 'pending') {
        const res = await api.get('/internships/admin/drafts/')
        setDrafts(res.data || [])
      } else if (activeTab === 'published') {
        const res = await api.get('/internships/?status=open')
        setPublishedList(res.data || [])
      } else if (activeTab === 'closed') {
        const res = await api.get('/internships/?status=closed')
        setClosedList(res.data || [])
      } else if (activeTab === 'history') {
        const res = await api.get('/internships/admin/history/')
        setHistoryList(res.data || [])
      }
    } catch (err) {
      console.error(err)
      setError('Could not load data for this section.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadTabData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab])

  // Import CDC Email Handler (FR-37, FR-38, FR-58)
  const handleImportSubmit = async (e, allowDuplicate = false) => {
    if (e) e.preventDefault()
    setImporting(true)
    setError('')
    setSuccessMsg('')
    setDuplicateWarning(null)

    try {
      const payload = {
        ...importForm,
        allow_duplicate: allowDuplicate,
      }

      const res = await api.post('/internships/admin/import/', payload)
      setSuccessMsg('Notice imported and extracted successfully! Ready for review.')
      setImportForm({
        email_subject: '',
        sender_email: 'cdc@diu.edu.bd',
        original_email_content: '',
        source_link: '',
      })

      // Immediately open draft for review
      openDraftForReview(res.data)
      loadStats()
    } catch (err) {
      if (err.response?.status === 409 && err.response?.data?.duplicate) {
        setDuplicateWarning(err.response.data)
      } else {
        setError(err.response?.data?.error || 'Failed to import notice. Please check inputs.')
      }
    } finally {
      setImporting(false)
    }
  }

  // Open Draft in Review Modal
  const openDraftForReview = (draft) => {
    setSelectedDraft(draft)
    setRejecting(false)
    setRejectReason('')

    const ext = draft.extraction_result || {}
    setReviewFields({
      company_name: ext.company_name || '',
      position: ext.position || draft.email_subject || '',
      description: ext.description || draft.original_email_content || '',
      eligibility: ext.eligibility || '',
      required_skills: Array.isArray(ext.required_skills)
        ? ext.required_skills.join(', ')
        : ext.required_skills || '',
      location: ext.location || '',
      employment_type: ext.employment_type || 'On-site',
      stipend: ext.stipend || '',
      application_deadline: ext.application_deadline || '',
      application_url: ext.application_url || draft.source_link || '',
      application_email: ext.application_email || '',
      application_instructions: ext.application_instructions || '',
    })
  }

  // Save Draft (PATCH)
  const handleSaveDraft = async () => {
    if (!selectedDraft) return
    try {
      const skillsArray = reviewFields.required_skills
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)

      const updatedResult = {
        ...selectedDraft.extraction_result,
        ...reviewFields,
        required_skills: skillsArray,
      }

      const res = await api.patch(`/internships/admin/drafts/${selectedDraft.id}/`, {
        extraction_result: updatedResult,
      })

      setSelectedDraft(res.data)
      alert('Draft changes saved successfully.')
      loadTabData()
    } catch {
      alert('Failed to save draft.')
    }
  }

  // Approve & Publish (FR-39)
  const handleApproveDraft = async () => {
    if (!selectedDraft) return

    if (selectedDraft.extraction_status === 'not_internship' && !reviewFields.is_internship_correction) {
      alert('This notice was classified as NOT an internship. You must explicitly check the Administrative Correction box before approving.')
      return
    }

    if (!reviewFields.company_name.trim() || !reviewFields.position.trim()) {
      alert('Company Name and Position Title are required before approving.')
      return
    }

    if (!window.confirm(`Are you sure you want to approve and publish "${reviewFields.position}" to students?`)) {
      return
    }

    try {
      const skillsArray = reviewFields.required_skills
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)

      const payload = {
        is_internship_correction: !!reviewFields.is_internship_correction,
        fields: {
          ...reviewFields,
          required_skills: skillsArray,
        },
      }

      await api.post(`/internships/admin/drafts/${selectedDraft.id}/approve/`, payload)
      alert('Internship approved and published successfully!')
      setSelectedDraft(null)
      loadTabData()
    } catch (err) {
      alert(err.response?.data?.error || 'Failed to approve internship.')
    }
  }

  // Reject Draft (FR-39)
  const handleRejectDraft = async () => {
    if (!selectedDraft) return

    try {
      await api.post(`/internships/admin/drafts/${selectedDraft.id}/reject/`, {
        reason: rejectReason || 'Rejected by administrator during verification.',
      })
      alert('Draft notice marked as rejected.')
      setSelectedDraft(null)
      loadTabData()
    } catch {
      alert('Failed to reject notice.')
    }
  }

  // Toggle status or delete published internship (FR-40)
  const handleToggleStatus = async (internship) => {
    const newStatus = internship.status === 'open' ? 'closed' : 'open'
    try {
      await api.patch(`/internships/admin/manage/${internship.id}/`, {
        status: newStatus,
      })
      loadTabData()
    } catch {
      alert('Failed to update status.')
    }
  }

  const handleDeleteInternship = async (internshipId) => {
    if (!window.confirm('Are you sure you want to permanently delete this internship?')) return
    try {
      await api.delete(`/internships/admin/manage/${internshipId}/`)
      loadTabData()
    } catch {
      alert('Failed to delete internship.')
    }
  }

  return (
    <div className="min-h-screen bg-slate-100 pb-20">
      {/* Top Navbar */}
      <nav className="flex flex-wrap items-center justify-between gap-4 bg-white px-6 py-4 shadow-sm md:px-10">
        <div className="flex items-center gap-3">
          <Link to="/dashboard" className="text-2xl font-bold text-blue-700">
            CampusWise
          </Link>
          <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-700">
            Administrator Portal
          </span>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/internships"
            className="rounded-lg border border-blue-600 px-4 py-2 text-sm font-semibold text-blue-600 hover:bg-blue-50"
          >
            🎓 View as Student
          </Link>
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
        {/* Navigation Tabs */}
        <div className="mb-6 flex flex-wrap gap-2 border-b border-gray-200 pb-2">
          {[
            { id: 'overview', label: '📊 Overview' },
            { id: 'import', label: '📥 Import CDC Email' },
            { id: 'pending', label: `⏳ Pending Review (${stats.pending_review})` },
            { id: 'published', label: `✅ Published (${stats.published_internships})` },
            { id: 'closed', label: `📁 Closed (${stats.closed_internships})` },
            { id: 'history', label: '📜 Import History' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`rounded-lg px-4 py-2.5 text-sm font-bold transition ${
                activeTab === tab.id
                  ? 'bg-blue-700 text-white shadow-sm'
                  : 'bg-white text-gray-600 hover:bg-gray-50 hover:text-gray-800'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* TAB 1: OVERVIEW & STATS */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
              <div className="rounded-xl bg-white p-5 shadow-sm border-t-4 border-blue-600">
                <p className="text-xs font-semibold text-gray-400 uppercase">Total Notices</p>
                <p className="mt-2 text-3xl font-extrabold text-gray-900">{stats.total_internships}</p>
              </div>
              <div className="rounded-xl bg-white p-5 shadow-sm border-t-4 border-green-600">
                <p className="text-xs font-semibold text-gray-400 uppercase">Published Live</p>
                <p className="mt-2 text-3xl font-extrabold text-green-700">{stats.published_internships}</p>
              </div>
              <div className="rounded-xl bg-white p-5 shadow-sm border-t-4 border-amber-500">
                <p className="text-xs font-semibold text-gray-400 uppercase">Pending Review</p>
                <p className="mt-2 text-3xl font-extrabold text-amber-600">{stats.pending_review}</p>
              </div>
              <div className="rounded-xl bg-white p-5 shadow-sm border-t-4 border-gray-400">
                <p className="text-xs font-semibold text-gray-400 uppercase">Closed / Expired</p>
                <p className="mt-2 text-3xl font-extrabold text-gray-700">{stats.closed_internships}</p>
              </div>
              <div className="rounded-xl bg-white p-5 shadow-sm border-t-4 border-red-500">
                <p className="text-xs font-semibold text-gray-400 uppercase">Rejected Imports</p>
                <p className="mt-2 text-3xl font-extrabold text-red-600">{stats.rejected_imports}</p>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="rounded-2xl bg-white p-8 shadow-sm">
              <h3 className="text-lg font-bold text-gray-900">Admin Workflow Shortcuts</h3>
              <p className="text-sm text-gray-500 mt-1">
                Import emails from Career Development Center (CDC), review Gemini AI extractions, or manage published postings.
              </p>

              <div className="mt-6 flex flex-wrap gap-4">
                <button
                  onClick={() => setActiveTab('import')}
                  className="rounded-xl bg-blue-700 px-6 py-3 font-semibold text-white shadow hover:bg-blue-800 transition"
                >
                  📥 Paste New CDC Email Notice
                </button>
                <button
                  onClick={() => setActiveTab('pending')}
                  className="rounded-xl border border-blue-600 px-6 py-3 font-semibold text-blue-700 hover:bg-blue-50 transition"
                >
                  ⏳ Review Pending Queue ({stats.pending_review})
                </button>
                <button
                  onClick={() => setActiveTab('published')}
                  className="rounded-xl border border-gray-300 px-6 py-3 font-semibold text-gray-700 hover:bg-gray-50 transition"
                >
                  📋 Manage Published Listings
                </button>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: IMPORT CDC EMAIL (FR-37, FR-38, FR-58) */}
        {activeTab === 'import' && (
          <div className="rounded-2xl bg-white p-8 shadow-sm">
            <h2 className="text-xl font-bold text-gray-900">Import CDC Email Notice</h2>
            <p className="mt-1 text-sm text-gray-500">
              Paste the text of an internship announcement email received from the university CDC. Google Gemini AI will automatically extract key structured fields and create a draft for your verification.
            </p>

            {error && <div className="mt-4 rounded-lg bg-red-50 p-4 text-sm text-red-700">{error}</div>}
            {successMsg && <div className="mt-4 rounded-lg bg-green-50 p-4 text-sm text-green-700">{successMsg}</div>}

            {/* Duplicate Notice Alert (FR-38) */}
            {duplicateWarning && (
              <div className="mt-4 rounded-xl border border-amber-300 bg-amber-50 p-5 text-amber-900">
                <h4 className="font-bold">⚠️ Duplicate Notice Detected</h4>
                <p className="mt-1 text-sm">
                  {duplicateWarning.message} (Previous Import ID: #{duplicateWarning.existing_id} - "{duplicateWarning.existing_subject}")
                </p>
                <div className="mt-4 flex gap-3">
                  <button
                    type="button"
                    onClick={() => handleImportSubmit(null, true)}
                    className="rounded-lg bg-amber-700 px-4 py-2 text-xs font-semibold text-white hover:bg-amber-800"
                  >
                    Import Anyway (Allow Duplicate)
                  </button>
                  <button
                    type="button"
                    onClick={() => setDuplicateWarning(null)}
                    className="rounded-lg bg-white px-4 py-2 text-xs font-semibold text-gray-700 border hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            <form onSubmit={handleImportSubmit} className="mt-6 space-y-5">
              <div>
                <label className="block text-sm font-semibold text-gray-700">Email Subject *</label>
                <input
                  type="text"
                  required
                  value={importForm.email_subject}
                  onChange={(e) => setImportForm({ ...importForm, email_subject: e.target.value })}
                  placeholder="e.g. Internship Opportunity for Software Engineering at BrainStation 23"
                  className="mt-1 w-full rounded-lg border border-gray-300 p-3 text-sm outline-none focus:border-blue-600"
                />
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <label className="block text-sm font-semibold text-gray-700">Sender Email (Optional)</label>
                  <input
                    type="email"
                    value={importForm.sender_email}
                    onChange={(e) => setImportForm({ ...importForm, sender_email: e.target.value })}
                    placeholder="cdc@diu.edu.bd"
                    className="mt-1 w-full rounded-lg border border-gray-300 p-3 text-sm outline-none focus:border-blue-600"
                  />
                </div>
                <div>
                  <label className="block text-sm font-semibold text-gray-700">Source Notice Link (Optional)</label>
                  <input
                    type="url"
                    value={importForm.source_link}
                    onChange={(e) => setImportForm({ ...importForm, source_link: e.target.value })}
                    placeholder="https://cdc.diu.edu.bd/notices/..."
                    className="mt-1 w-full rounded-lg border border-gray-300 p-3 text-sm outline-none focus:border-blue-600"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700">Original Email Content *</label>
                <textarea
                  required
                  rows={10}
                  value={importForm.original_email_content}
                  onChange={(e) => setImportForm({ ...importForm, original_email_content: e.target.value })}
                  placeholder="Paste the full raw email text as received from CDC here..."
                  className="mt-1 w-full rounded-lg border border-gray-300 p-3 font-mono text-sm outline-none focus:border-blue-600"
                />
              </div>

              <button
                type="submit"
                disabled={importing}
                className="rounded-xl bg-blue-700 px-8 py-3.5 font-bold text-white shadow-md hover:bg-blue-800 disabled:opacity-60 transition"
              >
                {importing ? '🤖 Extracting with Gemini AI...' : '✨ Import & Extract Information'}
              </button>
            </form>
          </div>
        )}

        {/* TAB 3: PENDING REVIEW QUEUE (FR-39) */}
        {activeTab === 'pending' && (
          <div className="rounded-2xl bg-white p-6 shadow-sm">
            <h2 className="text-xl font-bold text-gray-900">Pending Review Queue ({drafts.length})</h2>
            <p className="mt-1 text-sm text-gray-500">
              All imported emails remain in draft state until reviewed and approved by an administrator.
            </p>

            {loading ? (
              <p className="py-10 text-center text-gray-500">Loading pending drafts...</p>
            ) : drafts.length === 0 ? (
              <div className="py-12 text-center text-gray-500">
                <span className="text-4xl">🎉</span>
                <p className="mt-2 font-semibold">No pending drafts to review.</p>
              </div>
            ) : (
              <div className="mt-6 space-y-4">
                {drafts.map((draft) => {
                  const ext = draft.extraction_result || {}
                  return (
                    <div
                      key={draft.id}
                      className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-gray-200 p-5 hover:bg-slate-50 transition"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-800">
                            Draft #{draft.id}
                          </span>
                          <span
                            className={`rounded px-2 py-0.5 text-xs font-semibold ${
                              draft.extraction_status === 'success'
                                ? 'bg-green-100 text-green-800'
                                : 'bg-blue-100 text-blue-800'
                            }`}
                          >
                            Status: {draft.extraction_status}
                          </span>
                        </div>
                        <h4 className="mt-2 text-base font-bold text-gray-900">
                          {ext.position || draft.email_subject}
                        </h4>
                        <p className="text-sm text-gray-600">
                          Company: <span className="font-semibold">{ext.company_name || 'Pending Verification'}</span> • Deadline: {ext.application_deadline || 'None stated'}
                        </p>
                        <p className="text-xs text-gray-400 mt-1">
                          Imported on {new Date(draft.created_at).toLocaleString()}
                        </p>
                      </div>

                      <button
                        onClick={() => openDraftForReview(draft)}
                        className="rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-800 shadow-sm"
                      >
                        Review & Verify →
                      </button>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* TAB 4: PUBLISHED INTERNSHIPS (FR-40) */}
        {activeTab === 'published' && (
          <div className="rounded-2xl bg-white p-6 shadow-sm">
            <h2 className="text-xl font-bold text-gray-900">Live Published Internships ({publishedList.length})</h2>
            <p className="mt-1 text-sm text-gray-500">
              These postings are currently visible to enrolled students on their dashboard.
            </p>

            {loading ? (
              <p className="py-10 text-center text-gray-500">Loading published listings...</p>
            ) : publishedList.length === 0 ? (
              <p className="py-12 text-center text-gray-500">No active published internships.</p>
            ) : (
              <div className="mt-6 space-y-4">
                {publishedList.map((item) => (
                  <div
                    key={item.id}
                    className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-gray-200 p-5"
                  >
                    <div>
                      <h4 className="text-base font-bold text-gray-900">{item.position}</h4>
                      <p className="text-sm text-gray-600">
                        {item.company_name} • {item.location} • {item.employment_type}
                      </p>
                      <p className="text-xs text-gray-500 mt-1">
                        Deadline: <span className="font-semibold">{item.application_deadline || 'Open'}</span>
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      <Link
                        to={`/internships/${item.id}`}
                        className="rounded-lg border px-3 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-50"
                      >
                        View Public
                      </Link>
                      <button
                        onClick={() => handleToggleStatus(item)}
                        className="rounded-lg border border-amber-500 px-3 py-1.5 text-xs font-semibold text-amber-700 hover:bg-amber-50"
                      >
                        Mark as Closed
                      </button>
                      <button
                        onClick={() => handleDeleteInternship(item.id)}
                        className="rounded-lg border border-red-500 px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-50"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 5: CLOSED / EXPIRED INTERNSHIPS (FR-34) */}
        {activeTab === 'closed' && (
          <div className="rounded-2xl bg-white p-6 shadow-sm">
            <h2 className="text-xl font-bold text-gray-900">Closed & Expired Internships ({closedList.length})</h2>
            <p className="mt-1 text-sm text-gray-500">
              Notices whose application deadline has expired or were manually marked closed.
            </p>

            {loading ? (
              <p className="py-10 text-center text-gray-500">Loading closed listings...</p>
            ) : closedList.length === 0 ? (
              <p className="py-12 text-center text-gray-500">No closed internships in archive.</p>
            ) : (
              <div className="mt-6 space-y-4">
                {closedList.map((item) => (
                  <div
                    key={item.id}
                    className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-gray-200 bg-gray-50 p-5"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="rounded bg-red-100 px-2 py-0.5 text-xs font-bold text-red-700">
                          Closed
                        </span>
                        <h4 className="text-base font-bold text-gray-800">{item.position}</h4>
                      </div>
                      <p className="text-sm text-gray-600 mt-1">
                        {item.company_name} • Deadline: {item.application_deadline || 'Passed'}
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleToggleStatus(item)}
                        className="rounded-lg border border-green-600 px-3 py-1.5 text-xs font-semibold text-green-700 hover:bg-green-50"
                      >
                        Re-open
                      </button>
                      <button
                        onClick={() => handleDeleteInternship(item.id)}
                        className="rounded-lg border border-red-500 px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-50"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 6: AUDIT HISTORY (FR-41) */}
        {activeTab === 'history' && (
          <div className="rounded-2xl bg-white p-6 shadow-sm">
            <h2 className="text-xl font-bold text-gray-900">Import & Verification Audit History</h2>
            <p className="mt-1 text-sm text-gray-500">
              Comprehensive log of all CDC email imports, Gemini extraction statuses, and admin decisions.
            </p>

            {loading ? (
              <p className="py-10 text-center text-gray-500">Loading audit history...</p>
            ) : historyList.length === 0 ? (
              <p className="py-12 text-center text-gray-500">No import history found.</p>
            ) : (
              <div className="mt-6 divide-y divide-gray-100">
                {historyList.map((entry) => (
                  <div key={entry.id} className="py-4">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-gray-900 text-sm">
                        #{entry.id}: {entry.email_subject}
                      </span>
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-xs font-bold uppercase ${
                          entry.import_status === 'approved'
                            ? 'bg-green-100 text-green-800'
                            : entry.import_status === 'rejected'
                            ? 'bg-red-100 text-red-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        {entry.import_status}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      Sender: {entry.sender_email || 'CDC Direct'} • Imported on {new Date(entry.created_at).toLocaleString()}
                    </p>
                    {entry.rejection_reason && (
                      <p className="text-xs text-red-600 mt-1">
                        Reason for rejection: {entry.rejection_reason}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      {/* DRAFT REVIEW MODAL (FR-39, FR-58) */}
      {selectedDraft && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 overflow-y-auto">
          <div className="relative my-8 w-full max-w-5xl rounded-2xl bg-white p-6 shadow-2xl max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between border-b pb-4">
              <div>
                <h3 className="text-xl font-bold text-gray-900">
                  Verify & Edit Notice Draft #{selectedDraft.id}
                </h3>
                <p className="text-xs text-gray-500 mt-1">
                  Extraction Engine: <span className="font-semibold">{selectedDraft.extraction_status}</span>
                </p>
              </div>
              <button
                onClick={() => setSelectedDraft(null)}
                className="text-gray-400 hover:text-gray-600 text-2xl font-bold"
              >
                ×
              </button>
            </div>

            {/* Split View: Left (Original) vs Right (Extracted & Editable) */}
            <div className="mt-4 grid grid-cols-1 gap-6 md:grid-cols-2 overflow-y-auto pr-2 flex-1">
              {/* Left Column: Original Source Email */}
              <div className="rounded-xl bg-slate-50 p-4 border border-slate-200">
                <h4 className="text-xs font-bold uppercase text-slate-500 tracking-wider">
                  Original CDC Email Notice
                </h4>
                <div className="mt-3 text-xs space-y-2">
                  <p><strong>Subject:</strong> {selectedDraft.email_subject}</p>
                  <p><strong>Sender:</strong> {selectedDraft.sender_email || 'Unspecified'}</p>
                  {selectedDraft.source_link && (
                    <p>
                      <strong>Source:</strong>{' '}
                      <a href={selectedDraft.source_link} target="_blank" rel="noreferrer" className="text-blue-600 underline">
                        {selectedDraft.source_link}
                      </a>
                    </p>
                  )}
                </div>

                <div className="mt-4">
                  <label className="block text-xs font-bold text-slate-600 mb-1">
                    Raw Message Body
                  </label>
                  <pre className="h-96 overflow-y-auto rounded-lg border bg-white p-3 font-mono text-xs whitespace-pre-wrap text-gray-700">
                    {selectedDraft.original_email_content}
                  </pre>
                </div>
              </div>

              {/* Right Column: Editable Extracted Fields */}
              <div className="space-y-4">
                <h4 className="text-xs font-bold uppercase text-blue-700 tracking-wider">
                  Extracted Structured Information (Editable)
                </h4>

                {selectedDraft.extraction_status === 'not_internship' && (
                  <div className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
                    <p className="font-bold flex items-center gap-1 text-amber-800">
                      ⚠️ Classified as Non-Internship Notice
                    </p>
                    <p className="mt-1 text-gray-700">
                      This notice was classified as not an internship (e.g., permanent full-time vacancy or event).
                      To approve it as an internship, you must review all details and explicitly enable the administrative correction below.
                    </p>
                    <label className="mt-2.5 flex items-center gap-2 font-semibold text-amber-900 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={reviewFields.is_internship_correction || false}
                        onChange={(e) => setReviewFields({ ...reviewFields, is_internship_correction: e.target.checked })}
                        className="rounded text-blue-600 focus:ring-blue-500"
                      />
                      <span>Confirm administrative correction: Approve as an internship</span>
                    </label>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-gray-700">Company Name *</label>
                    <input
                      type="text"
                      value={reviewFields.company_name}
                      onChange={(e) => setReviewFields({ ...reviewFields, company_name: e.target.value })}
                      className="mt-1 w-full rounded border p-2 text-xs outline-none focus:border-blue-600"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-gray-700">Position Title *</label>
                    <input
                      type="text"
                      value={reviewFields.position}
                      onChange={(e) => setReviewFields({ ...reviewFields, position: e.target.value })}
                      className="mt-1 w-full rounded border p-2 text-xs outline-none focus:border-blue-600"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-gray-700">Description *</label>
                  <textarea
                    rows={4}
                    value={reviewFields.description}
                    onChange={(e) => setReviewFields({ ...reviewFields, description: e.target.value })}
                    className="mt-1 w-full rounded border p-2 text-xs outline-none focus:border-blue-600"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-gray-700">Workplace Type</label>
                    <select
                      value={reviewFields.employment_type}
                      onChange={(e) => setReviewFields({ ...reviewFields, employment_type: e.target.value })}
                      className="mt-1 w-full rounded border p-2 text-xs outline-none focus:border-blue-600"
                    >
                      <option value="On-site">On-site</option>
                      <option value="Remote">Remote</option>
                      <option value="Hybrid">Hybrid</option>
                      <option value="Full-time">Full-time</option>
                      <option value="Part-time">Part-time</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-gray-700">Location</label>
                    <input
                      type="text"
                      value={reviewFields.location}
                      onChange={(e) => setReviewFields({ ...reviewFields, location: e.target.value })}
                      className="mt-1 w-full rounded border p-2 text-xs outline-none focus:border-blue-600"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-gray-700">Stipend</label>
                    <input
                      type="text"
                      value={reviewFields.stipend}
                      onChange={(e) => setReviewFields({ ...reviewFields, stipend: e.target.value })}
                      placeholder="e.g. 15,000 BDT or Unpaid"
                      className="mt-1 w-full rounded border p-2 text-xs outline-none focus:border-blue-600"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-gray-700">Application Deadline (YYYY-MM-DD)</label>
                    <input
                      type="date"
                      value={reviewFields.application_deadline}
                      onChange={(e) => setReviewFields({ ...reviewFields, application_deadline: e.target.value })}
                      className="mt-1 w-full rounded border p-2 text-xs outline-none focus:border-blue-600"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-gray-700">Required Skills (Comma separated)</label>
                  <input
                    type="text"
                    value={reviewFields.required_skills}
                    onChange={(e) => setReviewFields({ ...reviewFields, required_skills: e.target.value })}
                    placeholder="Python, React, PostgreSQL"
                    className="mt-1 w-full rounded border p-2 text-xs outline-none focus:border-blue-600"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-gray-700">Application Portal URL</label>
                    <input
                      type="url"
                      value={reviewFields.application_url}
                      onChange={(e) => setReviewFields({ ...reviewFields, application_url: e.target.value })}
                      placeholder="https://..."
                      className="mt-1 w-full rounded border p-2 text-xs outline-none focus:border-blue-600"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-gray-700">Contact / HR Email</label>
                    <input
                      type="email"
                      value={reviewFields.application_email}
                      onChange={(e) => setReviewFields({ ...reviewFields, application_email: e.target.value })}
                      placeholder="hr@company.com"
                      className="mt-1 w-full rounded border p-2 text-xs outline-none focus:border-blue-600"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-gray-700">Application Instructions</label>
                  <textarea
                    rows={2}
                    value={reviewFields.application_instructions}
                    onChange={(e) => setReviewFields({ ...reviewFields, application_instructions: e.target.value })}
                    className="mt-1 w-full rounded border p-2 text-xs outline-none focus:border-blue-600"
                  />
                </div>
              </div>
            </div>

            {/* Modal Actions */}
            <div className="mt-6 border-t pt-4 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                {!rejecting ? (
                  <button
                    type="button"
                    onClick={() => setRejecting(true)}
                    className="rounded-lg border border-red-500 px-4 py-2 text-xs font-bold text-red-600 hover:bg-red-50"
                  >
                    Reject Notice
                  </button>
                ) : (
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      placeholder="Reason for rejection..."
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      className="rounded border p-1.5 text-xs outline-none"
                    />
                    <button
                      type="button"
                      onClick={handleRejectDraft}
                      className="rounded bg-red-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-red-700"
                    >
                      Confirm Reject
                    </button>
                    <button
                      type="button"
                      onClick={() => setRejecting(false)}
                      className="text-xs text-gray-500 underline"
                    >
                      Cancel
                    </button>
                  </div>
                )}
              </div>

              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={handleSaveDraft}
                  className="rounded-lg border border-gray-300 px-4 py-2 text-xs font-semibold text-gray-700 hover:bg-gray-50"
                >
                  Save Draft
                </button>
                <button
                  type="button"
                  onClick={handleApproveDraft}
                  className="rounded-lg bg-green-600 px-6 py-2 text-xs font-bold text-white shadow hover:bg-green-700"
                >
                  Approve and Publish to Students
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default AdminInternships
