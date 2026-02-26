"""Tests for the CodeDueProcess tools module."""

from codedueprocess.tools import calculate_stats, get_weather, search_web


class TestGetWeather:
    """Tests for get_weather tool."""

    def test_returns_formatted_string_with_city(self):
        """Should return a formatted string containing the city name."""
        result = get_weather.invoke({"city": "Paris"})
        assert "Paris" in result
        assert isinstance(result, str)

    def test_returns_weather_info_for_different_cities(self):
        """Should work for various city names."""
        cities = ["London", "New York", "Tokyo", "Paris"]
        for city in cities:
            result = get_weather.invoke({"city": city})
            assert city in result
            assert len(result) > 0


class TestSearchWeb:
    """Tests for search_web tool."""

    def test_returns_result_for_known_topic_langgraph(self):
        """Should return specific info for langgraph query."""
        result = search_web.invoke({"query": "langgraph"})
        assert "LangGraph" in result
        assert "Search Result:" in result

    def test_returns_result_for_known_topic_agent(self):
        """Should return specific info for agent query."""
        result = search_web.invoke({"query": "agent"})
        assert "autonomous agent" in result
        assert "Search Result:" in result

    def test_returns_result_for_known_topic_python(self):
        """Should return specific info for python query."""
        result = search_web.invoke({"query": "python"})
        assert "Python" in result
        assert "programming" in result
        assert "Search Result:" in result

    def test_returns_generic_result_for_unknown_topic(self):
        """Should return generic info for unknown queries."""
        result = search_web.invoke({"query": "xyzabc123nonexistent"})
        assert "generic information" in result
        assert "xyzabc123nonexistent" in result
        assert "Search Result:" in result

    def test_handles_case_insensitive_matching(self):
        """Should match topics regardless of case."""
        result_lower = search_web.invoke({"query": "langgraph"})
        result_upper = search_web.invoke({"query": "LANGGRAPH"})
        result_mixed = search_web.invoke({"query": "LangGraph"})

        assert "LangGraph" in result_lower
        assert "LangGraph" in result_upper
        assert "LangGraph" in result_mixed

    def test_handles_partial_matches(self):
        """Should match partial topic names."""
        result = search_web.invoke({"query": "learn about langgraph today"})
        assert "LangGraph" in result


class TestCalculateStats:
    """Tests for calculate_stats tool."""

    def test_returns_formatted_string_with_data(self):
        """Should return a string containing the input data identifier."""
        data = "sales_data_2024"
        result = calculate_stats.invoke({"data": data})
        assert data in result
        assert isinstance(result, str)

    def test_returns_stats_structure(self):
        """Should return stats with expected keys."""
        result = calculate_stats.invoke({"data": "any_dataset"})
        assert "Mean=" in result
        assert "Median=" in result
        assert "Mode=" in result

    def test_handles_empty_string(self):
        """Should handle empty string input gracefully."""
        result = calculate_stats.invoke({"data": ""})
        assert "" in result  # Empty string will be in result
        assert "Stats" in result

    def test_handles_special_characters_in_data(self):
        """Should handle special characters in data parameter."""
        data = "dataset-with_special.chars!@#"
        result = calculate_stats.invoke({"data": data})
        assert data in result
        assert "Stats" in result


class TestToolIntegration:
    """Integration tests for tools working together."""

    def test_all_tools_return_strings(self):
        """All tools should return string responses."""
        weather_result = get_weather.invoke({"city": "Paris"})
        search_result = search_web.invoke({"query": "python"})
        stats_result = calculate_stats.invoke({"data": "test_data"})

        assert isinstance(weather_result, str)
        assert isinstance(search_result, str)
        assert isinstance(stats_result, str)

    def test_tools_have_docstrings(self):
        """All tools should have proper docstrings."""
        assert get_weather.description is not None
        assert search_web.description is not None
        assert calculate_stats.description is not None
