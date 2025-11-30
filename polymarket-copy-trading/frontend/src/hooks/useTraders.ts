import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/utils/api-client'

interface TraderFilters {
    page?: number
    limit?: number
    timeframe?: '7d' | '30d' | 'all'
    min_pnl?: number
    min_win_rate?: number
    min_trades?: number
    search?: string
    sort_by?: string
    sort_order?: 'asc' | 'desc'
}

export function useTraders(filters: TraderFilters) {
    return useQuery({
        queryKey: ['traders', filters],
        queryFn: async () => {
            const { data } = await apiClient.get('/traders/leaderboard', { params: filters })
            return data
        },
    })
}

export function useTraderDetails(traderId: number) {
    return useQuery({
        queryKey: ['trader', traderId],
        queryFn: async () => {
            const { data } = await apiClient.get(`/traders/${traderId}`)
            return data
        },
        enabled: !!traderId,
    })
}

export function useTraderTrades(traderId: number) {
    return useQuery({
        queryKey: ['trader-trades', traderId],
        queryFn: async () => {
            const { data } = await apiClient.get(`/traders/${traderId}/trades`)
            return data
        },
        enabled: !!traderId,
    })
}

export function useCreateCopyRelationship() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: async (data: { trader_id: number; copy_percentage: number; max_investment_usd: number }) => {
            const response = await apiClient.post('/copy-relationships', data)
            return response.data
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['copy-relationships'] })
        },
    })
}
