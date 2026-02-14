# How to Use Mermaid Diagrams in Draw.io

## ✅ Recent Updates (Fixed Realistic Bot Capabilities)
- **REMOVED** unrealistic "Delete Message" actions  
- **ADDED** realistic bot capabilities sesuai Telegram Bot API limitations
- Files now contain **accurate bot action flows** yang bisa diimplementasikan

## 📋 Steps to Import in Draw.io:

### Method 1: Mermaid Import (Recommended)
1. Open **draw.io** (app.diagrams.net)
2. Click **"+ More shapes"** di sidebar kiri
3. Search dan enable **"Mermaid"** 
4. Drag **"Mermaid"** shape ke canvas
5. **Copy content** dari file `.mmd` dan paste di dialog Mermaid
6. Click **"Apply"**

### Method 2: Direct Text Import  
1. Open **draw.io**
2. Go to **File → Import from → Text**
3. Select **"Mermaid"** as format
4. **Copy paste** isi file `.mmd` 
5. Click **"Import"**

### Method 3: Insert Advanced
1. Open **draw.io**
2. Go to **Insert → Advanced → Mermaid**
3. Paste diagram code
4. Click **"Insert"**

## 📁 Available Files:

### `complete-system-flow-drawio.mmd` 
- **Detailed version** dengan comprehensive node coverage
- **Updated with realistic actions**: Reply warnings, report to admin, flag untuk review
- **Best for**: Documentation, detailed analysis

### `complete-system-flow-drawio-simple.mmd`  
- **Simplified version** optimized untuk readability
- **Realistic bot capabilities** sesuai Telegram API constraints
- **Best for**: Presentations, overview diagrams

## 🔄 Key Changes Made:

### ❌ Removed Unrealistic Actions:
- ~~Delete Message~~ (Bot tidak bisa delete user messages)
- ~~Delete Original Message~~ (Requires admin privileges)

### ✅ Added Realistic Actions:
- **⚠️ Reply Warning** to suspicious message
- **🚨 Report to Admin Group** untuk escalation
- **📢 Public Warning** general announcement  
- **💬 Caution Reply** untuk suspicious content
- **👨‍💼 Admin Review Queue** untuk manual checking

## 🎨 Post-Import Tips:

1. **Resize canvas**: Diagram might be large, adjust zoom
2. **Customize colors**: Dapat customize styling setelah import  
3. **Export options**: PNG, PDF, SVG tersedia
4. **Edit mode**: Double-click untuk edit Mermaid code

## 🔧 Troubleshooting:

- **Error "Unknown diagram type"**: Pastikan tidak ada ````mermaid` markers
- **Layout issues**: Try different layout options di Mermaid settings
- **Missing shapes**: Enable Mermaid plugin di More shapes

## 📌 Implementation Note:

Diagram sekarang reflect **realistic Telegram bot capabilities**:
- Bot dapat **reply** ke messages
- Bot dapat **send notifications** ke admin group  
- Bot dapat **log incidents** ke database
- Bot **TIDAK DAPAT** delete messages from other users (unless admin with specific permissions)

Ready to implement! 🚀