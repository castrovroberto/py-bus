import React from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Link
} from 'react-router-dom';
import HomePage from './pages/HomePage';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-100 text-gray-800">
        <nav className="bg-blue-600 text-white p-4 shadow-md">
          <ul className="flex space-x-4">
            <li>
              <Link to="/" className="hover:text-blue-200">Home</Link>
            </li>
            <li>
              <Link to="/dashboard" className="hover:text-blue-200">Dashboard</Link>
            </li>
            <li>
              <Link to="/login" className="hover:text-blue-200">Login</Link>
            </li>
            {/* Add more nav links as needed, e.g., for Admin, Logout */}
          </ul>
        </nav>

        <main className="p-4">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            {/* Add more routes, including protected routes */}
          </Routes>
        </main>

        <footer className="bg-gray-200 text-center p-4 mt-auto">
          <p>&copy; {new Date().getFullYear()} Modbus Integration Suite</p>
        </footer>
      </div>
    </Router>
  );
}

export default App;
