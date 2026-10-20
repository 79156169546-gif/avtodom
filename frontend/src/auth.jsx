import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { fetchMe, getToken, login, logout, register, setToken } from './api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(Boolean(getToken()))

  // Восстанавливаем сессию после перезагрузки страницы.
  useEffect(() => {
    if (!getToken()) {
      setLoading(false)
      return
    }
    let alive = true
    fetchMe()
      .then((data) => {
        if (alive) setUser(data)
      })
      .catch(() => {
        setToken('')
        if (alive) setUser(null)
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [])

  const handleAuth = useCallback((result) => {
    setToken(result.token)
    setUser(result.user)
    return result.user
  }, [])

  const signIn = useCallback(
    async (email, password) => handleAuth(await login({ email, password })),
    [handleAuth],
  )

  const signUp = useCallback(
    async (payload) => handleAuth(await register(payload)),
    [handleAuth],
  )

  const signOut = useCallback(async () => {
    try {
      await logout()
    } catch {
      /* сессия уже недействительна — молча чистим локально */
    }
    setToken('')
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({
      user,
      loading,
      isOwner: user?.role === 'owner',
      signIn,
      signUp,
      signOut,
    }),
    [user, loading, signIn, signUp, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth должен вызываться внутри AuthProvider')
  return context
}
