import numpy as np
import pandas as pd
import geopandas as gp
import pytest
import dask.dataframe as dd
from hypothesis import given
import hypothesis.strategies as hs

import spatialpandas as sp
from spatialpandas import GeoDataFrame
from spatialpandas.dask import DaskGeoDataFrame
from tests.geometry.strategies import st_point_array, st_polygon_array
from tests.test_parquet import hyp_settings


@given(
    st_point_array(min_size=1, geoseries=True),
    st_polygon_array(min_size=1, geoseries=True),
    hs.sampled_from(["inner", "left", "right"])
)
@hyp_settings
def test_sjoin(gp_points, gp_polygons, how):
    # join with geopandas
    left_gpdf = gp.GeoDataFrame({
        'geometry': gp_points,
        'a': np.arange(10, 10 + len(gp_points)),
        'c': np.arange(20, 20 + len(gp_points)),
        'v': np.arange(30, 30 + len(gp_points)),
    }).set_index('a')

    right_gpdf = gp.GeoDataFrame({
        'geometry': gp_polygons,
        'a': np.arange(10, 10 + len(gp_polygons)),
        'b': np.arange(20, 20 + len(gp_polygons)),
        'v': np.arange(30, 30 + len(gp_polygons)),
    }).set_index('b')

    # Generate expected result as geopandas GeoDataFrame
    gp_expected = gp.sjoin(left_gpdf, right_gpdf, how=how)
    gp_expected = gp_expected.rename(columns={"v_x": "v_left", "v_y": "v_right"})
    if how == "right":
        gp_expected.index.name = right_gpdf.index.name
    else:
        gp_expected.index.name = left_gpdf.index.name

    # join with spatialpandas
    left_spdf = GeoDataFrame(left_gpdf)
    right_spdf = GeoDataFrame(right_gpdf)

    result = sp.sjoin(
        left_spdf, right_spdf, how=how
    ).sort_values(['v_left', 'v_right'])
    assert isinstance(result, GeoDataFrame)

    # Check pandas results
    if len(gp_expected) == 0:
        assert len(result) == 0
    else:
        expected = GeoDataFrame(gp_expected).sort_values(['v_left', 'v_right'])
        pd.testing.assert_frame_equal(expected, result)

        # left_df as Dask frame
        left_spddf = dd.from_pandas(left_spdf, npartitions=4)

        if how == "right":
            # Right join not supported when left_df is a Dask DataFrame
            with pytest.raises(ValueError):
                sp.sjoin(left_spddf, right_spdf, how=how)
            return
        else:
            result_ddf = sp.sjoin(
                left_spddf, right_spdf, how=how
            )
        assert isinstance(result_ddf, DaskGeoDataFrame)
        assert result_ddf.npartitions <= 4
        result = result_ddf.compute().sort_values(['v_left', 'v_right'])
        pd.testing.assert_frame_equal(expected, result)
