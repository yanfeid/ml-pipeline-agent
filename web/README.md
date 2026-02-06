# RMR Agent Web Frontend

Next.js frontend for the RMR Agent ML Pipeline Automation tool.

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn
- Backend API running on http://localhost:8000

### Installation

```bash
cd web
npm install
```

### Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Production Build

```bash
npm run build
npm start
```

## Project Structure

```
web/
├── src/
│   ├── app/              # Next.js App Router
│   │   ├── layout.tsx    # Root layout
│   │   ├── page.tsx      # Main page
│   │   └── globals.css   # Global styles
│   ├── components/       # React components
│   │   ├── Sidebar.tsx
│   │   ├── WelcomePage.tsx
│   │   ├── WorkflowProgress.tsx
│   │   ├── ComponentVerification.tsx
│   │   ├── DagVerification.tsx
│   │   └── ResultsPage.tsx
│   ├── hooks/            # Custom React hooks
│   │   └── useWorkflow.ts
│   └── lib/              # Utilities
│       └── api.ts        # API client
├── package.json
├── tailwind.config.ts
└── tsconfig.json
```

## Features

- GitHub repository URL input with ML file detection
- Real-time workflow progress tracking
- Component verification UI with edit capabilities
- DAG YAML editor with preview mode
- Pull request result display

## API Integration

The frontend proxies API requests to the FastAPI backend:

- `POST /api/detect-ml-files` - Detect ML files in repo
- `POST /api/run-workflow` - Start/continue workflow
- `GET /api/workflow-status/{repo_name}` - Get workflow status
- `POST /api/cancel-workflow/{repo_name}` - Cancel workflow
