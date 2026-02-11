import { useState } from 'react'
import axios from 'axios'
import './App.css'

function App() {
  const [file, setFile] = useState(null)
  const [events, setEvents] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [isSyncing, setIsSyncing] = useState(false)

  const handleFileChange = (e) => {
    setFile(e.target.files[0])
  }

  const handleUpload = async () => {
    if (!file) return alert("Please select a file first!")
    setIsLoading(true)
    const formData = new FormData()
    formData.append("file", file)

    try {
      const response = await axios.post("http://127.0.0.1:8000/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      setEvents(response.data.events) 
    } catch (error) {
      console.error("Error uploading:", error)
      alert("Failed to extract dates.")
    } finally {
      setIsLoading(false)
    }
  }

  const handleEdit = (index, field, value) => {
    const updatedEvents = [...events]
    updatedEvents[index][field] = value
    setEvents(updatedEvents)
  }

  const handleDelete = (index) => {
    const updatedEvents = events.filter((_, i) => i !== index)
    setEvents(updatedEvents)
  }

  // --- NEW: Sync to Google Calendar ---
  const handleAddToCalendar = async () => {
    if (!confirm("This will open a Google Login window on your server. Check your terminal if nothing happens!")) return;

    setIsSyncing(true)
    try {
        const response = await axios.post("http://127.0.0.1:8000/create_events", events)
        alert(response.data.message)
    } catch (error) {
        console.error("Sync Error:", error)
        alert("Failed to sync. Check the backend terminal for details.")
    } finally {
        setIsSyncing(false)
    }
  }

  return (
    <div style={{ padding: "40px", maxWidth: "900px", margin: "0 auto", fontFamily: "sans-serif" }}>
      <h1>📅 SyllaSync</h1>
      
      <div style={{ padding: "20px", border: "2px dashed #ccc", borderRadius: "10px", textAlign: "center", marginBottom: "30px" }}>
        <input type="file" accept=".pdf" onChange={handleFileChange} />
        <button onClick={handleUpload} disabled={isLoading} style={{ marginLeft: "10px", padding: "10px 20px" }}>
          {isLoading ? "Analyzing..." : "Upload & Extract"}
        </button>
      </div>

      {events.length > 0 && (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2>Review Your Schedule</h2>
            <button 
              onClick={handleAddToCalendar}
              disabled={isSyncing}
              style={{ backgroundColor: "#4285F4", color: "white", padding: "10px 20px", border: "none", borderRadius: "5px", cursor: "pointer" }}
            >
              {isSyncing ? "Syncing..." : "Add to Google Calendar 📅"}
            </button>
          </div>

          <table style={{ width: "100%", borderCollapse: "collapse", marginTop: "20px" }}>
            <thead>
              <tr style={{ background: "#f4f4f4", textAlign: "left" }}>
                <th style={{ padding: "10px" }}>Event Name</th>
                <th style={{ padding: "10px" }}>Date (YYYY-MM-DD)</th>
                <th style={{ padding: "10px" }}>Weight</th>
                <th style={{ padding: "10px" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event, index) => (
                <tr key={index} style={{ borderBottom: "1px solid #eee" }}>
                  <td><input value={event.title} onChange={(e) => handleEdit(index, "title", e.target.value)} style={{ width: "100%" }} /></td>
                  <td><input value={event.date} onChange={(e) => handleEdit(index, "date", e.target.value)} style={{ width: "100%" }} /></td>
                  <td><input value={event.weight} onChange={(e) => handleEdit(index, "weight", e.target.value)} style={{ width: "60px" }} /></td>
                  <td style={{ textAlign: "center" }}><button onClick={() => handleDelete(index)}>❌</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default App