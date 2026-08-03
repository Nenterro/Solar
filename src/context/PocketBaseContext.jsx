import { createContext, useContext, useEffect, useState } from 'react';
import PocketBase from 'pocketbase';

const PB_URL = 'http://100.97.146.42:8090'; // User's home server IP
const pb = new PocketBase(PB_URL);

const PocketBaseContext = createContext();

export function PocketBaseProvider({ children }) {
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    // Simple health check to verify connection
    pb.health.check().then(() => setIsConnected(true)).catch(() => setIsConnected(false));
  }, []);

  return (
    <PocketBaseContext.Provider value={{ pb, isConnected }}>
      {children}
    </PocketBaseContext.Provider>
  );
}

export function usePocketBase() {
  return useContext(PocketBaseContext);
}
