import React from 'react';
import { Outlet } from 'react-router';
import { Sidebar } from '../components/Sidebar';

export function Root() {
  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: '#0a0c0f' }}>
      <Sidebar />
      <main
        style={{
          flex: 1,
          minWidth: 0,
          overflowY: 'auto',
          overflowX: 'hidden',
          padding: 24,
          backgroundColor: '#0a0c0f',
        }}
      >
        <Outlet />
      </main>
    </div>
  );
}
