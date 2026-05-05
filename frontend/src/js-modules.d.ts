/**
 * Ambient module shims so `checkJs` resolves `baseUrl` imports (see jsconfig.json).
 */
declare module 'components/common' {
  import type { FC, ReactNode } from 'react'

  export const Button: FC<any>
  export const Input: FC<any>
  export const VerticalLayout: FC<{ children?: ReactNode }>
  export const Header: FC<{ title?: string; children?: ReactNode }>
  export const Content: FC<{ children?: ReactNode }>
  export const ButtonLink: FC<any>
}

declare module 'backendApi' {
  export function listArtists(): Promise<unknown[]>
  export function refreshArtists(onlyMissingImages?: boolean): Promise<{
    updated: number
    total: number
    message?: string
  }>
  export function createArtist(payload: unknown): Promise<unknown>
  export function deleteArtist(artistId: string | number): Promise<unknown>
  export function patchArtistTidalId(
    artistId: string | number,
    tidalId: string | null | undefined
  ): Promise<unknown>
  export function searchTidalArtists(query: string, limit?: number): Promise<unknown[]>
  export function getTidalSession(): Promise<{ logged_in?: boolean } | null>
}
