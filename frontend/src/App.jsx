import { useState } from 'react'
import axios from 'axios'
import './App.css'
import { useGoogleLogin } from '@react-oauth/google'

// Google Calendar Colors
const COLORS = [
  { id: "1", name: "Lavender", hex: "#7986cb" },
  { id: "2", name: "Sage", hex: "#33b679" },
  { id: "3", name: "Grape", hex: "#8e24aa" },
  { id: "4", name: "Flamingo", hex: "#e67c73" },
  { id: "5", name: "Banana", hex: "#f09300" }, // Yellow
  { id: "6", name: "Tangerine", hex: "#f4511e" },
  { id: "7", name: "Peacock", hex: "#039be5" }, // Cyan
  { id: "8", name: "Graphite", hex: "#616161" },
  { id: "9", name: "Blueberry", hex: "#3f51b5" }, // Blue
  { id: "10", name: "Basil", hex: "#0b8043" }, // Green
  { id: "11", name: "Tomato", hex: "#d50000" }, // Red
]

function App() {
  const [courses, setCourses] = useState([]) 
  const [isLoading, setIsLoading] = useState(false)
  const [isSyncing, setIsSyncing] = useState(false)
  const [isExporting, setIsExporting] = useState(false);
  const [userToken, setUserToken] = useState(null);
  
  // --- GOOGLE LOGIN ---
  const login = useGoogleLogin({
    onSuccess: (codeResponse) => {
      console.log("Login Success!", codeResponse);
      setUserToken(codeResponse.access_token);
      alert("Successfully logged in with Google!");
    },
    onError: (error) => console.log('Login Failed:', error),
    // We must ask for Calendar and Sheets permissions here!
    scope: "https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/spreadsheets",
  });
  
  // New State for Reminders
  const [addReminders, setAddReminders] = useState(true)

  // Calculate Total Weight for a Course
  const calculateTotalWeight = (events) => {
    let total = 0
    events.forEach(event => {
      const cleanString = event.weight.toString().replace(/[^0-9.]/g, '')
      const number = parseFloat(cleanString)
      if (!isNaN(number)) {
        total += number
      }
    })
    return Math.round(total * 100) / 100
  }

  // Handle Multiple Files
  const handleUpload = async (e) => {
    const files = Array.from(e.target.files)
    if (files.length === 0) return
    setIsLoading(true)
    for (const file of files) {
      const formData = new FormData()
      formData.append("file", file)
      try {
        const response = await axios.post("http://127.0.0.1:8000/upload", formData)
        if (response.data) {
            const { course, events } = response.data
            setCourses(prev => [...prev, {
                id: Date.now() + Math.random(),
                name: course || "New Course",
                color: "9", 
                events: events || []
            }])
        } 
      } catch (error) {
        console.error(`Error uploading ${file.name}:`, error)
        alert(`Failed to upload ${file.name}`)
      }
    }
    setIsLoading(false)
  }

  // Update Course Color
  const handleColorChange = (courseId, newColorId) => {
    setCourses(courses.map(c => c.id === courseId ? { ...c, color: newColorId } : c))
  }

  // Edit Course Name
  const handleCourseNameChange = (courseId, newName) => {
    setCourses(courses.map(c => c.id === courseId ? { ...c, name: newName } : c))
  }

  // Delete a Course
  const deleteCourse = (courseId) => {
    setCourses(courses.filter(c => c.id !== courseId))
  }

  // Edit an Event
  const handleEventEdit = (courseId, eventIndex, field, value) => {
    const updatedCourses = [...courses]
    const course = updatedCourses.find(c => c.id === courseId)
    course.events[eventIndex][field] = value
    setCourses(updatedCourses)
  }

  // Delete an Event
  const deleteEvent = (courseId, eventIndex) => {
    const updatedCourses = [...courses]
    const course = updatedCourses.find(c => c.id === courseId)
    course.events = course.events.filter((_, i) => i !== eventIndex)
    setCourses(updatedCourses)
  }

  // Add a Manual Event
  const addEvent = (courseId) => {
    const updatedCourses = [...courses]
    const course = updatedCourses.find(c => c.id === courseId)
    course.events.push({
        title: "New Assignment",
        date: "", // Blank date for picker
        weight: "0%"
    })
    setCourses(updatedCourses)
  }

  // Add Manual Course
  const addManualCourse = () => {
    setCourses(prev => [...prev, {
        id: Date.now() + Math.random(),
        name: "New Course",
        color: "1",
        events: [] 
    }])
  }

  // --- UPDATED SYNC FUNCTION ---
  const handleAddToCalendar = async () => {
    if (!userToken) {
      alert("Please sign in with Google first!");
      return;
    }

    setIsSyncing(true)
    let validEvents = []
    let skippedCount = 0

    courses.forEach(course => {
      course.events.forEach(event => {
        if (event.date) {
          validEvents.push({
            title: event.title, date: event.date, weight: event.weight, course: course.name, colorId: course.color
          })
        } else {
          skippedCount++
        }
      })
    })

    if (validEvents.length === 0) {
      alert("No events with dates found to sync.")
      setIsSyncing(false)
      return
    }

    const message = skippedCount > 0
      ? `Found ${validEvents.length} events to sync (skipping ${skippedCount} without dates). Proceed?`
      : `Add ${validEvents.length} events to Google Calendar?`

    if (!confirm(message)) {
      setIsSyncing(false)
      return
    }

    try {
      const payload = {
        events: validEvents,
        addReminders: addReminders,
        token: userToken // <-- WE SEND THE TOKEN HERE
      }
      const response = await axios.post("http://127.0.0.1:8000/create_events", payload)
      alert(response.data.message)
    } catch (error) {
      console.error("Sync Error:", error)
      alert("Failed to sync. Make sure you are logged in!")
    } finally {
      setIsSyncing(false)
    }
  }

  // --- UPDATED EXPORT FUNCTION ---
  const handleExportToSheets = async () => {
    if (!userToken) {
      alert("Please sign in with Google first!");
      return;
    }

    setIsExporting(true);
    try {
      let allEvents = [];
      courses.forEach(course => {
        course.events.forEach(event => {
          allEvents.push({
            title: event.title, date: event.date, weight: event.weight, course: course.name
          });
        });
      });

      if (allEvents.length === 0) {
        alert("No events found to export.");
        setIsExporting(false);
        return;
      }

      const payload = {
        events: allEvents,
        token: userToken // <-- WE SEND THE TOKEN HERE TOO
      };
      const response = await axios.post("http://127.0.0.1:8000/export_sheets", payload);

      if (response.data.url) {
        window.open(response.data.url, '_blank', 'noopener,noreferrer');
      }
    } catch (error) {
      console.error("Error exporting to sheets:", error);
      alert("Failed to export to Google Sheets. Make sure you are logged in!");
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div style={{ padding: "40px", maxWidth: "1000px", margin: "0 auto", fontFamily: "sans-serif" }}>
      <h1>SyllaSync Semester Planner</h1>

      {/* --- GOOGLE LOGIN SECTION ADDED HERE --- */}
      <div style={{ textAlign: "center", marginBottom: "20px" }}>
        {!userToken ? (
          <button 
            onClick={() => login()}
            style={{ backgroundColor: "white", color: "#444", padding: "10px 20px", border: "1px solid #ccc", borderRadius: "8px", cursor: "pointer", fontSize: "1.1rem", fontWeight: "bold", display: "inline-flex", alignItems: "center", gap: "10px" }}
          >
            <img src="https://upload.wikimedia.org/wikipedia/commons/5/53/Google_%22G%22_Logo.svg" alt="Google Logo" width="20" />
            Sign in with Google
          </button>
        ) : (
          <div style={{ backgroundColor: "#d4edda", color: "#155724", padding: "10px", borderRadius: "8px", display: "inline-block", fontWeight: "bold" }}>
            ✅ Connected to Google
          </div>
        )}
      </div>
      
      {/* Upload Box */}
      <div style={{ padding: "30px", border: "4px solid #ccc", borderRadius: "15px", textAlign: "center", marginBottom: "30px", background: "#423636" }}>
        <h3 style={{ color: "white" }}>Upload All Your Syllabi</h3>
        <input 
          type="file" 
          accept=".pdf" 
          multiple 
          onChange={handleUpload} 
          disabled={isLoading}
          style={{ display: "none" }}
          id="fileInput"
        />
        <label htmlFor="fileInput" style={{ 
          background: "#333", color: "white", padding: "10px 20px", borderRadius: "5px", cursor: "pointer", fontSize: "1.2rem"
        }}>
          {isLoading ? "Analyzing Files..." : "Select PDF Files (Upload Multiple)"}
        </label>
        <p style={{ marginTop: "10px", color: "#ccc" }}>Select all your course PDFs at once.</p>
      </div>

      {courses.length > 0 && (
        <div>
          {/* Review Header with Reminder Checkbox & Both Action Buttons */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
            <h2></h2>
            
            <div style={{ display: "flex", alignItems: "center", gap: "15px" }}>
                {/* REMINDER CHECKBOX */}
                <label style={{ 
                    display: "flex", 
                    alignItems: "center", 
                    gap: "10px", 
                    cursor: "pointer", 
                    fontWeight: "bold",
                    background: "#423636", 
                    padding: "10px 15px",
                    borderRadius: "8px",
                    border: "2px solid #ccc",
                    boxShadow: "0 2px 4px rgba(0,0,0,0.05)"
                }}>
                    <input 
                        type="checkbox" 
                        checked={addReminders}
                        onChange={(e) => setAddReminders(e.target.checked)}
                        style={{ width: "18px", height: "18px", accentColor: "#423636", cursor: "pointer" }}
                    />
                    Add Study Reminders
                </label>

                {/* EXPORT TO SHEETS BUTTON */}
                <button 
                  onClick={handleExportToSheets}
                  disabled={isExporting}
                  style={{ backgroundColor: "#0F9D58", color: "white", padding: "12px 20px", border: "none", borderRadius: "8px", cursor: "pointer", fontSize: "1.1rem", fontWeight: "bold" }}
                >
                  {isExporting ? "Exporting..." : "Export to Sheets"}
                </button>

                {/* SYNC TO CALENDAR BUTTON */}
                <button 
                  onClick={handleAddToCalendar}
                  disabled={isSyncing}
                  style={{ backgroundColor: "#4285F4", color: "white", padding: "12px 20px", border: "none", borderRadius: "8px", cursor: "pointer", fontSize: "1.1rem", fontWeight: "bold" }}
                >
                  {isSyncing ? "Syncing..." : "Sync to Calendar"}
                </button>
            </div>
          </div>
                
          {courses.map(course => {
            const totalWeight = calculateTotalWeight(course.events)
            const isPerfect = totalWeight === 100
            const isOver = totalWeight > 100
            const statusColor = isPerfect ? "lightgreen" : (isOver ? "red" : "orange")
            const statusIcon = isPerfect ? "✅" : (isOver ? "🛑" : "⚠️")
            
            return (
                <div key={course.id} style={{ border: "1px solid #ddd", borderRadius: "10px", marginBottom: "30px", overflow: "hidden", boxShadow: "0 2px 5px rgba(0,0,0,0.1)" }}>
                
                {/* Course Header */}
                <div style={{ padding: "15px", background: "#423636", display: "flex", justifyContent: "space-between", alignItems: "center", color: "white" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "15px", flex: 1 }}>
                    
                    <input 
                        value={course.name}
                        onChange={(e) => handleCourseNameChange(course.id, e.target.value)}
                        style={{
                            background: "transparent",
                            border: "none",
                            borderBottom: "1px dashed #777",
                            color: "white",
                            fontSize: "1.5rem",
                            fontWeight: "bold",
                            width: "100%",
                            maxWidth: "300px",
                            outline: "none"
                        }}
                    />
                    
                    <div style={{ 
                        background: "#333", 
                        padding: "5px 10px", 
                        borderRadius: "15px", 
                        border: `2px solid ${statusColor}`,
                        color: statusColor,
                        fontWeight: "bold",
                        fontSize: "0.9rem",
                        whiteSpace: "nowrap"
                    }}>
                        {totalWeight}% {statusIcon}
                    </div>

                    <select 
                        value={course.color} 
                        onChange={(e) => handleColorChange(course.id, e.target.value)}
                        style={{ padding: "5px", borderRadius: "5px", border: "1px solid #ccc" }}
                    >
                        {COLORS.map(c => (
                        <option key={c.id} value={c.id} style={{ color: c.hex, fontWeight: "bold" }}>
                            {c.name}
                        </option>
                        ))}
                    </select>
                    </div>
                    <button onClick={() => deleteCourse(course.id)} style={{ color: "#ff6b6b", border: "none", background: "#2b2222", cursor: "pointer", fontWeight: "bold", padding: "5px 10px", borderRadius: "5px", marginLeft: "10px" }}>Delete</button>
                </div>

                {/* Events Table */}
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                    <tbody>
                    {course.events.map((event, index) => (
                        <tr key={index} style={{ borderBottom: "1px solid #eee" }}>
                        
                        {/* Title Input */}
                        <td style={{ padding: "10px" }}>
                            <input 
                                value={event.title} 
                                onChange={(e) => handleEventEdit(course.id, index, "title", e.target.value)} 
                                style={{ width: "100%", border: "none" }} 
                            />
                        </td>
                        
                        {/* Date Picker Input */}
                        <td style={{ padding: "10px" }}>
                            <input 
                                type="date"
                                value={event.date} 
                                onChange={(e) => handleEventEdit(course.id, index, "date", e.target.value)} 
                                style={{ width: "100%", border: "none", fontFamily: "inherit" }} 
                            />
                        </td>

                        {/* Weight Input */}
                        <td style={{ padding: "10px" }}>
                            <input 
                                value={event.weight} 
                                onChange={(e) => handleEventEdit(course.id, index, "weight", e.target.value)} 
                                style={{ width: "50px", border: "none" }} 
                            />
                        </td>
                        
                        {/* Delete Button */}
                        <td style={{ padding: "10px" }}>
                            <button onClick={() => deleteEvent(course.id, index)} style={{ cursor: "pointer", border: "none", background: "none" }}>❌</button>
                        </td>
                        </tr>
                    ))}
                    </tbody>
                </table>
                
                {/* Add Event Button */}
                <div style={{ padding: "10px", textAlign: "center", background: "#423636", borderTop: "1px solid #eee" }}>
                    <button 
                        onClick={() => addEvent(course.id)}
                        style={{
                            background: "none",
                            border: "2px solid #ccc",
                            color: "#a08a8a",
                            padding: "8px 20px",
                            borderRadius: "5px",
                            cursor: "pointer",
                            width: "50%",
                            fontWeight: "bold"
                        }}
                    >
                        + Add Event
                    </button>
                </div>

                </div>
            )
          })}
        </div>
      )}

      {/* --- ADD CLASS BUTTON (At bottom) --- */}
      <div style={{ textAlign: "center", marginTop: "40px", paddingBottom: "40px" }}>
        <button 
            onClick={addManualCourse}
            style={{
                background: "#555",
                color: "white",
                padding: "15px 30px",
                borderRadius: "8px",
                cursor: "pointer",
                fontSize: "1.2rem",
                fontWeight: "bold",
                border: "2px dashed #777",
                width: "100%",
                maxWidth: "400px"
            }}
        >
            ➕ Add Another Course
        </button>
      </div>

    </div>
  )
}

export default App