import { useState } from 'react'
import axios from 'axios'
import './App.css'

function App() {
  const [file, setFile] = useState(null)
  const [events, setEvents] = useState([])
  const [isLoading, setIsLoading] = useState(false)

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

  // --- NEW: Function to handle editing text ---
  const handleEdit = (index, field, value) => {
    const updatedEvents = [...events]
    updatedEvents[index][field] = value
    setEvents(updatedEvents)
  }

  // --- NEW: Function to delete a row ---
  const handleDelete = (index) => {
    const updatedEvents = events.filter((_, i) => i !== index)
    setEvents(updatedEvents)
  }

  // --- NEW: Placeholder for Calendar Sync ---
  const handleAddToCalendar = () => {
    console.log("Final Data to Sync:", events)
    alert("Check the console! This data is ready to be sent to Google.")
  }

  return (
    <div style={{ padding: "40px", fontFamily: "Arial, sans-serif", maxWidth: "900px", margin: "0 auto" }}>
      <h1>📅 SyllaSync</h1>
      
      {/* Upload Box */}
      <div style={{ padding: "20px", border: "2px dashed #ccc", borderRadius: "10px", textAlign: "center", marginBottom: "30px" }}>
        <input type="file" accept=".pdf" onChange={handleFileChange} />
        <button 
          onClick={handleUpload} 
          disabled={isLoading} 
          style={{ marginLeft: "10px", padding: "10px 20px", cursor: "pointer" }}
        >
          {isLoading ? "Analyzing..." : "Upload & Extract"}
        </button>
      </div>

      {/* Editable Table */}
      {events.length > 0 && (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2>Review Your Schedule</h2>
            <button 
              onClick={handleAddToCalendar}
              style={{ backgroundColor: "#4285F4", color: "white", padding: "10px 20px", border: "none", borderRadius: "5px", cursor: "pointer" }}
            >
              Add to Google Calendar 📅
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
                  <td style={{ padding: "10px" }}>
                    <input 
                      value={event.title} 
                      onChange={(e) => handleEdit(index, "title", e.target.value)}
                      style={{ width: "100%", padding: "5px" }}
                    />
                  </td>
                  <td style={{ padding: "10px" }}>
                    <input 
                      type="text" 
                      value={event.date} 
                      onChange={(e) => handleEdit(index, "date", e.target.value)}
                      style={{ width: "100%", padding: "5px" }}
                    />
                  </td>
                  <td style={{ padding: "10px" }}>
                    <input 
                      value={event.weight} 
                      onChange={(e) => handleEdit(index, "weight", e.target.value)}
                      style={{ width: "60px", padding: "5px" }}
                    />
                  </td>
                  <td style={{ padding: "10px", textAlign: "center" }}>
                    <button 
                      onClick={() => handleDelete(index)}
                      style={{ background: "none", border: "none", cursor: "pointer", fontSize: "16px" }}
                    >
                      ❌
                    </button>
                  </td>
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