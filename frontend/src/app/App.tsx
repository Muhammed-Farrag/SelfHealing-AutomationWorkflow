import React, { useState } from 'react';
import { RouterProvider } from 'react-router';
import { router } from './routes';
import { LoadingScreen } from './components/LoadingScreen';

export default function App() {
  const [loading, setLoading] = useState(true);

  if (loading) {
    return <LoadingScreen onComplete={() => setLoading(false)} />;
  }

  return <RouterProvider router={router} />;
}
